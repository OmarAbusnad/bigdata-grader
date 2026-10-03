FROM python:3.12-bookworm

ARG SPARK_VERSION=3.5.1
ARG HADOOP_VERSION=3

RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless bash curl git procps socat tini ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Keep a compatible Spark runtime available even when the student does not vendor spark-submit.
RUN python -m pip install --no-cache-dir "pyspark==${SPARK_VERSION}" pymongo==4.17.0

RUN ln -s /usr/local/bin/python /usr/local/bin/py \
    && useradd --create-home --uid 10001 student \
    && mkdir -p /workspace /grader-tests /tmp/student-home \
    && chown -R student:student /workspace /grader-tests /tmp/student-home

ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["bash"]
