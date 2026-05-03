"""Default web UI (Streamlit-based).

Launch with:
    praxia ui
or:
    streamlit run -m praxia.ui.app
"""
from praxia.ui import launcher

__all__ = ["launcher"]
