"""Default web UI (Streamlit-based).

Launch with:
    agentloom ui
or:
    streamlit run -m agentloom.ui.app
"""
from agentloom.ui import launcher

__all__ = ["launcher"]
