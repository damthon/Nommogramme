"""Le point d'entrée de l'exécutable, et son contrôle intégré.

``packaging/lanceur.py`` n'est pas dans le paquet installable : c'est le
script que PyInstaller analyse pour construire l'exécutable. Il est donc
chargé ici par son chemin.

Ce qu'on y vérifie tient en une phrase : **ce fichier ne s'exécute jamais
dans les conditions où il est testé.** Il tourne sur un poste Windows, dans
un paquet gelé, sur une machine sans Python. Tout ce qui dépend de
l'environnement y est donc un risque, et les deux tests ci-dessous portent
sur les deux pièges déjà rencontrés — chacun découvert en production, aucun
par la suite de tests.
"""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest

_CHEMIN = Path(__file__).resolve().parent.parent / "packaging" / "lanceur.py"


@pytest.fixture(scope="module")
def lanceur():
    """Charge ``packaging/lanceur.py``, qui n'est pas un module du paquet."""
    if not _CHEMIN.exists():  # pragma: no cover - dépend de la copie de travail
        pytest.skip(f"{_CHEMIN} absent")
    specification = importlib.util.spec_from_file_location("lanceur", _CHEMIN)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class TestSortieConsole:
    """La console Windows ne parle pas la même langue que le calcul."""

    def test_les_symboles_du_domaine_passent_en_cp1252(self, lanceur, monkeypatch) -> None:
        """θ, μ et les exposants n'existent pas dans la page de code Windows.

        Sous Windows, la console hérite de cp1252 en Europe de l'Ouest.
        ``print(f"θ_cr = {…}")`` y lève ``UnicodeEncodeError`` et arrête le
        programme — alors que le calcul, lui, s'est bien passé. Le défaut est
        invisible sous Linux et macOS, où la sortie est en UTF-8 : il n'est
        apparu que sur le coureur Windows de l'intégration continue.

        Le test reconstitue la console fautive et vérifie que la
        reconfiguration la rend inoffensive.
        """
        cp1252 = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        monkeypatch.setattr(sys, "stdout", cp1252)
        monkeypatch.setattr(sys, "stderr", cp1252)

        # Sans la reconfiguration, l'écriture échoue.
        with pytest.raises(UnicodeEncodeError):
            cp1252.write("θ_cr = 617 °C")

        lanceur._sortie_en_utf8()
        sys.stdout.write("θ_cr = 617 °C · μ₀ = 0,41 · A_m/V = 116 m⁻¹")

    def test_la_reconfiguration_ne_casse_pas_sur_un_flux_exotique(
        self, lanceur, monkeypatch
    ) -> None:
        """Un flux sans ``reconfigure`` — redirection, capture — est toléré.

        La fonction est appelée au tout début du programme : si elle levait,
        l'application ne démarrerait pas du tout, ce qui serait bien pire que
        le problème qu'elle règle.
        """

        class _FluxSansReconfigure:
            def write(self, texte: str) -> int:
                return len(texte)

            def flush(self) -> None:
                pass

        monkeypatch.setattr(sys, "stdout", _FluxSansReconfigure())
        monkeypatch.setattr(sys, "stderr", _FluxSansReconfigure())
        lanceur._sortie_en_utf8()


class TestAutotest:
    """Le contrôle que l'intégration continue exécute sur le paquet compilé."""

    def test_il_reussit_sur_une_installation_saine(self, lanceur, capsys) -> None:
        pytest.importorskip("matplotlib")
        pytest.importorskip("tkinter", reason="l'autotest exige les modules de l'écran")
        pytest.importorskip("PIL.ImageTk")
        assert lanceur.autotest() == 0
        assert "Autotest réussi" in capsys.readouterr().out

    def test_il_echoue_si_un_module_differe_manque(self, lanceur, monkeypatch) -> None:
        """C'est sa raison d'être : PIL._tkinter_finder avait été oublié.

        Un paquet PyInstaller se compile sans erreur quand un import différé
        lui échappe. Rien ne le signale avant que l'utilisateur ne lance
        l'application et ne voie une fenêtre vide.
        """
        vrai_import = importlib.import_module

        def _import_qui_manque(nom: str, *args, **kwargs):
            if nom == "PIL._tkinter_finder":
                raise ImportError("simulation d'un module absent du paquet")
            return vrai_import(nom, *args, **kwargs)

        monkeypatch.setattr(importlib, "import_module", _import_qui_manque)
        assert lanceur.autotest() == 1

    def test_il_echoue_si_le_catalogue_est_amputé(self, lanceur, monkeypatch) -> None:
        """L'autre panne classique : les fichiers de données non embarqués."""
        pytest.importorskip("matplotlib")
        pytest.importorskip("tkinter", reason="l'autotest exige les modules de l'écran")
        pytest.importorskip("PIL.ImageTk")
        from nommogramme.interface import saisie

        monkeypatch.setattr(saisie, "noms_par_famille", lambda: {"IPE": ("IPE 300",)})
        assert lanceur.autotest() == 1
