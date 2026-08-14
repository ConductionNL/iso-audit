"""Configuratie-oplossing met vastgelegde precedence en herkomst.

`settings.load_config()` is de enige plek die bepaalt welke waarde wint. Alles wat
configuratie nodig heeft, vraagt het hier — niet rechtstreeks aan `os.environ`, want dan
is de herkomst weg en kan een auditor niet meer zien waar zijn instelling vandaan komt.
"""

from iso_audit.config.herkomst import log_herkomst, masker
from iso_audit.config.settings import Bron, Settings, Waarde, load_config

__all__ = ["Bron", "Settings", "Waarde", "load_config", "log_herkomst", "masker"]
