FROM python:3.12-slim

WORKDIR /app

# Install linters available via apt/pip. For project-specific tools (npx eslint,
# go vet, cargo clippy, dotnet format, rubocop, phpstan), mount the host project
# and rely on the host toolchain (containerized linting across 8 languages is a
# separate project).
RUN pip install --no-cache-dir ruff pylint

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

ENV GATE_HOST=0.0.0.0
ENV GATE_PORT=7733
EXPOSE 7733

CMD ["python", "server.py"]
