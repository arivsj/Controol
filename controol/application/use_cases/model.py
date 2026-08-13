"""ModelProbeUseCase: regra do modelo exibido no footer (nunca o harness)."""
from __future__ import annotations


class ModelProbeUseCase:
    """Detecta o modelo real do harness sem rodar um prompt."""

    def detect(self, harness) -> str | None:
        """Probe sem custo (config do harness ou última sessão); não fixa nada."""
        return harness.probe_model()

    def label(self, harness_model, probe) -> str:
        """O modelo exibido: config/detectado tem prioridade, senão o probe."""
        return harness_model or probe or "—"
