# The whole suite in one image: Python, pinned dependencies and the Playwright browsers.
# Run it against any Gitea, no local Python needed:
#
#   docker build -t qualitylens .
#   docker run --rm --network host qualitylens doctor
#   docker run --rm --network host -v "$PWD/results:/suite/results" qualitylens run fast --record
#   docker run --rm -e QL_BASE_URL=https://gitea.example.com -e QL_ADMIN_PASSWORD=... qualitylens run smoke
#
# Same base image as the visual suite (Makefile), so screenshots match the approved baselines.
FROM mcr.microsoft.com/playwright/python:v1.56.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /suite
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN pip install --no-deps . \
 && useradd --create-home --uid 10001 qa \
 && mkdir -p results test-history allure-results \
 && chown -R qa /suite
USER qa

ENTRYPOINT ["qualitylens"]
CMD ["run", "smoke"]
