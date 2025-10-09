from .cards import register_callbacks as cards_callbacks
from .options import register_callbacks as options_callbacks
from .results import register_callbacks as results_callbacks
from .stores import register_callbacks as stores_callbacks


def register_callbacks(app):
    cards_callbacks(app)
    options_callbacks(app)
    results_callbacks(app)
    stores_callbacks(app)

