import os
from flask import Flask, render_template, request
import psycopg2
from psycopg2.extras import RealDictCursor

# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

app = Flask(__name__)


def setup_tracing():
    """Configure OpenTelemetry tracing and auto-instrumentation."""
    service_name = os.getenv("OTEL_SERVICE_NAME", "registration-app")
    # Base endpoint (no path)
    base_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://adot-apm-collector.adot-system.svc.cluster.local:4318",
    )

    # HTTP exporter needs the /v1/traces path
    endpoint = f"{base_endpoint.rstrip('/')}/v1/traces"

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": os.getenv("OTEL_SERVICE_NAMESPACE", "demo"),
            "deployment.environment": os.getenv("OTEL_ENVIRONMENT", "dev"),
        }
    )

    provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(
        endpoint=endpoint,
        # you can also set timeout/compression here if needed
    )
    span_processor = BatchSpanProcessor(span_exporter)
    provider.add_span_processor(span_processor)
    trace.set_tracer_provider(provider)

    # Instrument Flask and psycopg2
    FlaskInstrumentor().instrument_app(app)
    Psycopg2Instrumentor().instrument()


def get_db_conn():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        port=os.environ.get("DB_PORT", "5432"),
        cursor_factory=RealDictCursor,
    )


def init_db():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS registrations (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    cur.close()
    conn.close()


# ---- Initialize tracing + DB at import time (Flask 3-compatible) ----
setup_tracing()
init_db()
# ---------------------------------------------------------------------


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")

        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO registrations (full_name, email) VALUES (%s, %s);",
            (full_name, email),
        )
        conn.commit()
        cur.close()
        conn.close()

        return render_template("register.html", submitted=True, full_name=full_name)

    return render_template("register.html", submitted=False)


if __name__ == "__main__":
    # Local dev only; in Kubernetes we use gunicorn
    app.run(host="0.0.0.0", port=8000)
