# iso-audit portaal-image.
#
# Twee stages: builder installeert de dependencies met `uv sync --frozen` tegen de
# gecommitte uv.lock (nooit pip, nooit een naked install), runtime draait als
# non-root met een read-only rootfilesystem.
#
# WeasyPrint-systeembibliotheken zitten in de runtime-stage. Dat is geen detail:
# zonder libpango/libcairo/libgdk-pixbuf faalt de memo-render pas op het moment dat
# een auditor op exporteren drukt — dus in productie, niet in CI.

# Op digest gepind, niet op tag. `ghcr.io/astral-sh/uv` publiceert geen
# versie-specifieke `<versie>-python3.12-bookworm-slim`-tags — alleen een floating
# tag die onder je handen kan wijzigen. Een digest maakt de build reproduceerbaar en
# de herkomst controleerbaar, wat hier de hele reden is dat we dit image gebruiken.
# Bumpen: pull de tag, lees de nieuwe digest, vervang hem hier, met CHANGELOG-regel.
# Overeenkomend met tag python3.12-bookworm-slim, opgehaald 2026-08-12.
FROM ghcr.io/astral-sh/uv@sha256:5d275ca5f0da33c3368ac8fbb85fafabad023b3b8a7cff39a94ac0baecfd9a50 AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Eerst alleen de lock + manifest, zodat de dependency-laag gecachet blijft zolang
# die twee niet wijzigen.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
RUN uv sync --frozen --no-dev


# Idem op digest; overeenkomend met tag python:3.12-slim-bookworm, 2026-08-12.
FROM python@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS runtime

# WeasyPrint-runtime + fonts. `--no-install-recommends` houdt het oppervlak klein.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Vaste uid/gid; fsGroup 10001 in deployment.yaml sluit hierop aan zodat de
# non-root app op de PVC mag schrijven.
RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app src ./src
# examples/norms wordt door `iso-audit ui --norms` gelezen; examples/auditmemo
# levert het profiel- en memo-input-voorbeeld waar de deploy-README naar verwijst.
COPY --chown=app:app examples ./examples

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Fail closed is de default, ook als het manifest hem zou vergeten.
    REQUIRE_AUTH=true

USER app

# 8081 is waar oauth2-proxy naartoe praat. Puur documentatie: de app bindt
# 127.0.0.1 (zie de --host in deployment.yaml), dus deze poort is niet vanaf het
# pod-netwerk bereikbaar — en dat is precies de bedoeling.
EXPOSE 8081

ENTRYPOINT ["iso-audit"]
# Zonder args geeft `iso-audit` zijn help. De echte argumenten staan in
# deployment.yaml, expliciet en zichtbaar, niet verstopt in een image-default:
# `iso-audit ui` heeft geen env-fallbacks en eist --session/--profile/--norms/
# --memo-input.
CMD ["--help"]
