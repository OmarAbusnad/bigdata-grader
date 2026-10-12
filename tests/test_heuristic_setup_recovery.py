from grader.heuristic_setup_recovery import allow_clean_database_retry

CONFLICT = ('pymongo.errors.OperationFailure: An existing index has the same name '
            'as the requested index, codeName IndexKeySpecsConflict')


def make_repo(tmp_path, readme='Run with: uvicorn api:app'):
    (tmp_path / 'README.md').write_text(readme)
    return tmp_path


def ok(repo, **changes):
    opts=dict(
        plan_source='heuristic',
        setup_command='python src/mongo_setup.py',
        setup_succeeded=True,
        unique_index_exists=True,
        failed_returncode=1,
        timed_out=False,
        error_output=CONFLICT,
        data_written=False,
    )
    opts.update(changes)
    return allow_clean_database_retry(repo, **opts)


def test_inferred_undocumented_setup_index_conflict_allows_one_proof_retry(tmp_path):
    assert ok(make_repo(tmp_path))


def test_explicit_readme_setup_is_never_skipped(tmp_path):
    assert not ok(make_repo(tmp_path, 'python src/mongo_setup.py\npython main.py --file sample.csv'))


def test_student_error_or_data_written_is_not_masked(tmp_path):
    repo=make_repo(tmp_path)
    assert not ok(repo,error_output='TypeError: wrong function argument')
    assert not ok(repo,data_written=True)
    assert not ok(repo,timed_out=True)
    assert not ok(repo,setup_succeeded=False)
    assert not ok(repo,unique_index_exists=False)
    assert not ok(repo,failed_returncode=0)
    assert not ok(repo,setup_command=None)
    assert not ok(repo,plan_source='readme')


def test_readme_explicit_module_setup_is_not_skipped(tmp_path):
    assert not ok(make_repo(tmp_path,'python -m src.mongo_setup\n'),setup_command='python -m src.mongo_setup')


def test_no_arbitrary_retry_on_missing_dependency(tmp_path):
    repo=make_repo(tmp_path)
    assert not ok(repo,error_output='ModuleNotFoundError: No module named pymongo')
