# P26 — unsafe to reuse older frozen source in targeted regrade

Evidence from two original GitHub Actions artifacts:
- [Baseline matrix run 37874152827](https://github.com/omrbosnd/bigdata-grader/actions/runs/37874152827), artifact `unified-P26-37874152827`: student source commit `51605d72971468f5d96fb995833f378a87d2216f`.
- [Later accepted grading run 38317234359](https://github.com/omrbosnd/bigdata-grader/actions/runs/38317234359), artifact `late-grading-P26-38317234359`: student source commit `fc4f5d9924fe9a59f09e4167d323eaf4672ccca2`.
- [Initial frozen artifact](https://github.com/omrbosnd/bigdata-grader/actions/runs/37390623044): `frozen-P26-37390623044` dates from before the accepted late submission.

These sources are **not the same immutable code version**. A recovered Spark assertion from old `37390623044` freeze **must not** be merged into the newer P26 grade derived from `fc4f5d99...`.

**Safe follow-up:** First obtain or reproducibly freeze the exact `fc4f5d99...` commit, link it to the corresponding later assessment and documented Spark deficit, then run only that failed Spark stage after verifying compatible Scala/Spark connector prerequisites. Do not use current HEAD, silently substitute the old archive, or overwrite historic PASS. This is a precondition, not a newly proven student failure.

No new P26 student test or academic grade update performed.
