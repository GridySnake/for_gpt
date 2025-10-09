# =========================================================
# === Imports
# =========================================================
from dash import Dash
from secure_middleware_for_dash import AuthMiddleware
from .strategies_blocks import get_strategies_layout
from .callbacks import register_callbacks
from .assets.clientside_callbacks import register_clientside_callbacks

# =========================================================
# === App, Config & Layout
# =========================================================
strategies_app = Dash(
    __name__,
    requests_pathname_prefix="/strategies/",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    external_stylesheets=[
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css",
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css",
    ],
    suppress_callback_exceptions=True,
)

# Register Python callbacks
register_callbacks(strategies_app)

# Register JS (clientside) callbacks
register_clientside_callbacks(strategies_app)

# Layout
strategies_app.layout = get_strategies_layout()

# Secure
secured_strategies_app = AuthMiddleware(strategies_app.server)
