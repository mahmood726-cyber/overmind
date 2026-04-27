# Overmind Procedures

Automatically discovered fix recipes from nightly verification outcomes.

## Proven Recipes

| Recipe | Pattern | Fix | Seen | Resolved | Confidence | Last Seen |
|--------|---------|-----|------|----------|------------|-----------|
| TIMEOUT:advanced-n | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 19 | 1 | 6% | 2026-04-26 |

## Candidates (unproven)

| Recipe | Pattern | Fix | Seen | Resolved | Last Seen |
|--------|---------|-----|------|----------|-----------|
| CONFIGURATION:evidence-i | no tests ran in 0.03s | Check pytest configuration (testpaths, test file naming, col | 2 | 0 | 2026-04-11 |
| CONFIGURATION:idea12-592 | validation.run_quick_validatio | Verify column names in validation.run_quick_validation match | 2 | 0 | 2026-04-13 |
| DEPENDENCY_ROT:io | io.loaders | Check if io.loaders is installed: pip install io.loaders | 2 | 0 | 2026-04-26 |
| DEPENDENCY_ROT:statistical_framework | statistical_framework | Check if statistical_framework is installed: pip install sta | 2 | 0 | 2026-04-08 |
| MISSING_FIXTURE:pairwise70 | ck, subtests, tmp_path, tmp_pa | Check test for unregistered fixture parameters and ensure re | 2 | 0 | 2026-04-12 |
| SYNTAX_ERROR:ipd-qma-pr | e 418
    """
    ^
SyntaxErro | Fix the syntax error in the reported file | 2 | 0 | 2026-04-08 |
| SYNTAX_ERROR:repo300-en | ix
               ^
SyntaxErro | Fix the syntax error in the reported file | 2 | 0 | 2026-04-13 |
| UNKNOWN:pairwise70 | ck, subtests, tmp_path, tmp_pa | Manual investigation needed | 2 | 0 | 2026-04-10 |
| DEPENDENCY_ROT:cardioorac | mal_cdf, load_data)
ImportErro | Check if shared is installed: pip install shared | 1 | 0 | 2026-04-13 |
| DEPENDENCY_ROT:denominato | py:src.dclnma.witnesses.base: | Break circular import by moving WitnessContext to a separate | 1 | 0 | 2026-04-20 |
| DEPENDENCY_ROT:kmcurve-68 | import process_pdf
ImportErro | Check if the missing module is installed: pip install the mi | 1 | 0 | 2026-04-25 |
| DEPENDENCY_ROT:registry-f | ============================= | Check the import chain in tests/test_meta.py and install any | 1 | 0 | 2026-04-11 |
| DEPENDENCY_ROT:user-ecc0a | <module>
    raise ImportErro | Check if the missing module is installed: pip install the mi | 1 | 0 | 2026-04-19 |
| MISSING_FIXTURE:ipd-meta-p | test.py': [Errno 2] No such fi | Restore or regenerate the missing file: t open file | 1 | 0 | 2026-04-13 |
| MISSING_FIXTURE:pub-bias-s | ERROR: file or directory not f | Create tests/test_smoke.py or update the test command to poi | 1 | 0 | 2026-04-15 |
| MISSING_FIXTURE:ubcma-4230 | newline="",
    )
FileNotFou | Restore or regenerate the missing file: , line 873, in get_h | 1 | 0 | 2026-04-08 |
| SYNTAX_ERROR:metasprint | aph preparation
 ^

SyntaxErro | Fix the syntax error in the reported file | 1 | 0 | 2026-04-15 |
| TEST_FAILURE:asreview-5 | tiple_raters_fleiss
2 failed, | Read test output and fix failing tests | 1 | 0 | 2026-04-09 |
| TEST_FAILURE:bayesianma | 0_r_code - Asser...
7 failed, | Read test output and fix failing tests | 1 | 0 | 2026-04-17 |
| TEST_FAILURE:ctgov-sear | est_ci_bounds_valid
20 failed, | Read test output and fix failing tests | 1 | 0 | 2026-04-09 |
| TEST_FAILURE:dataextrac | OMPLETE: 82 passed, 2 failed
S | Read test output and fix failing tests | 1 | 0 | 2026-04-25 |
| TEST_FAILURE:esc-acs-li | Error: assert 15...
1 failed i | Read test output and fix failing tests | 1 | 0 | 2026-04-26 |
| TEST_FAILURE:fatiha-pro | nstalling renv  ... FAILED | Read test output and fix failing tests | 1 | 0 | 2026-04-25 |
| TEST_FAILURE:globalst-5 | truthcert_integrity
4 failed i | Read test output and fix failing tests | 1 | 0 | 2026-04-09 |
| TIMEOUT:asreview-5 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:bayesianma | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:cardio-ctg | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:cardioorac | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-10 |
| TIMEOUT:cbamm-0820 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:cbamm-0820 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-26 |
| TIMEOUT:cbamm-c5df | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-19 |
| TIMEOUT:dataextrac | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:dta70-4b17 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:esc-acs-li | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:evidence-i | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:evidence-i | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-26 |
| TIMEOUT:evidenceor | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:experiment | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:fatiha-pro | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:globalst-5 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:grma-paper | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:hfn786-583 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:hfpef-regi | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:html-apps- | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-17 |
| TIMEOUT:idea12-592 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:ipd-meta-p | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:ipd-qma-pr | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:lec-phase0 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-09 |
| TIMEOUT:llm-meta-a | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:meta-ecosy | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-10 |
| TIMEOUT:metaoverfi | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:metasprint | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-09 |
| TIMEOUT:mlmresearc | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:moonshot-e | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:nma-a6e8ac | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:nma-c44d8a | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-09 |
| TIMEOUT:overmind-b | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:pairwise70 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:prognostic | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-10 |
| TIMEOUT:pub-bias-s | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-10 |
| TIMEOUT:rct-extrac | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:registry-f | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:repo300-en | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:rmstnma-18 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:superapp-3 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-09 |
| TIMEOUT:transcende | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-15 |
| TIMEOUT:truthcert- | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:ubcma-4230 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:user-ecc0a | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-17 |
| UNKNOWN:denominato | py:src.dclnma.witnesses.base: | Manual investigation needed | 1 | 1 | 2026-04-25 |
| UNKNOWN:hta-eviden | no tests ran in 2.35s | Manual investigation needed | 1 | 0 | 2026-04-09 |
