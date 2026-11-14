"""L'aide au focus clavier : présente quand on tabule, discrète sinon.

Le test porte sur la logique de la bulle, avec un faux champ : ouvrir un
second interprète Tk à côté de celui des tests de la fenêtre fait planter
Python au ramasse-miettes, sous Windows.
"""

from __future__ import annotations

from nommogramme.interface.infobulle import Infobulle


class _Champ:
    """Ce dont l'infobulle se sert d'un widget ; ``after`` exécute aussitôt."""

    def bind(self, *_args, **_kwargs) -> None:
        pass

    def after(self, _ms, fonction):
        fonction()
        return "tache"

    def after_cancel(self, _tache) -> None:
        pass

    def winfo_rootx(self) -> int:
        return 0

    def winfo_rooty(self) -> int:
        return 0

    def winfo_height(self) -> int:
        return 20


class _Bulle(Infobulle):
    """Montrer et cacher sans fenêtre : on note seulement l'état."""

    def montrer(self) -> None:
        self._tache = None
        self._fenetre = True

    def cacher(self) -> None:
        self._fenetre = None


def test_le_clavier_montre_le_clic_non_la_frappe_efface() -> None:
    bulle = _Bulle(_Champ(), texte="aide")
    touche = type("Evenement", (), {"keysym": "a"})()

    bulle._sur_focus()
    assert bulle.visible, "arrivée au clavier : la bulle doit paraître"

    bulle._sur_frappe(touche)
    assert not bulle.visible, "on tape : la bulle doit s'effacer"

    bulle._sur_clic()
    bulle._sur_focus()
    assert not bulle.visible, "focus donné par un clic : pas de bulle"

    bulle._sur_perte_focus()
    bulle._sur_focus()
    assert bulle.visible, "après une sortie, le clavier montre de nouveau la bulle"


def test_les_aides_voisines_s_enchainent_sans_delai(monkeypatch) -> None:
    """Une aide vient de se fermer : la suivante s'ouvre aussitôt au survol."""
    import time

    from nommogramme.interface import infobulle as module

    delais = []

    class _Mesure(_Champ):
        def after(self, ms, fonction):
            delais.append(ms)
            return "tache"

    bulle = _Bulle(_Mesure(), texte="aide")
    monkeypatch.setattr(module, "_derniere_fermeture", float("-inf"))
    bulle._sur_entree()
    monkeypatch.setattr(module, "_derniere_fermeture", time.monotonic())
    bulle._sur_entree()
    assert delais == [bulle.delai_ms, 0]


def test_tabuler_ne_ferme_pas_la_bulle() -> None:
    bulle = _Bulle(_Champ(), texte="aide")
    bulle._sur_focus()
    bulle._sur_frappe(type("Evenement", (), {"keysym": "Tab"})())
    assert bulle.visible
