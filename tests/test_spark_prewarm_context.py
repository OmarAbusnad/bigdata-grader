from grader.sandbox import DockerSandbox, SandboxConfig


def _sandbox(tmp_path):
    root=tmp_path/"student"
    root.mkdir()
    (root/"requirements.txt").write_text("pyspark==3.5.1\npymongo>=4.6\n",encoding="utf-8")
    (root/"spark_loader.py").write_text(
        'PACKAGE="org.mongodb.spark:mongo-spark-connector_2.12:10.3.0"\n'
        'df.write.format("mongodb").save()\n',encoding="utf-8")
    hidden=tmp_path/"hidden"
    hidden.mkdir()
    return DockerSandbox(tmp_path,"TEST",root,hidden,SandboxConfig())


def test_prewarm_opt_in_declaration_only(tmp_path,monkeypatch):
    sandbox=_sandbox(tmp_path)
    monkeypatch.setenv("GRADER_PREWARM_SPARK","1")
    sandbox.prepare_build_context()
    image=(sandbox.build_context/".grader.Dockerfile").read_text(encoding="utf-8")
    script=(sandbox.build_context/".grader.spark-prewarm.sh").read_text(encoding="utf-8")
    assert "RUN bash /workspace/.grader.spark-prewarm.sh" in image
    assert "--packages \"$packages\"" in script
    assert "GRADER_SPARK_PREFETCH_RC" in script
    assert sandbox._spark_prefetch["enabled"] is True
    assert "10.3.0" in (sandbox.build_context/".grader.spark-prefetch.txt").read_text()
    assert (sandbox.build_context/".grader.spark-cache-only.py").read_text().strip()=='print("GRADER_SPARK_PACKAGE_CACHE_ONLY")'


def test_prewarm_off_by_default(tmp_path,monkeypatch):
    sandbox=_sandbox(tmp_path)
    monkeypatch.delenv("GRADER_PREWARM_SPARK",raising=False)
    sandbox.prepare_build_context()
    assert sandbox._spark_prefetch["enabled"] is False
    assert not (sandbox.build_context/".grader.spark-prefetch.txt").exists()
    assert "RUN bash /workspace/.grader.spark-prewarm.sh" not in (sandbox.build_context/".grader.Dockerfile").read_text()
