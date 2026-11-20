import pytest


@pytest.fixture(autouse=True)
def sem_chaves_reais(monkeypatch):
    """Nenhum teste usa a chave real do .env nem gasta créditos da Tavily.
    setenv+delenv fazem o monkeypatch registrar o estado original e restaurá-lo
    no fim, mesmo que algum teste chame carregar() e leia o .env."""
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.delenv("TAVILY_API_KEY")
    monkeypatch.setattr("athena.config.carregar_env", lambda caminho: None)
