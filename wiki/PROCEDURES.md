# Overmind Procedures

Automatically discovered fix recipes from nightly verification outcomes.

## Proven Recipes

| Recipe | Pattern | Fix | Seen | Resolved | Confidence | Last Seen |
|--------|---------|-----|------|----------|------------|-----------|
| TIMEOUT:advanced-n | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 9 | 1 | 17% | 2026-04-13 |

## Candidates (unproven)

| Recipe | Pattern | Fix | Seen | Resolved | Last Seen |
|--------|---------|-----|------|----------|-----------|
| CONFIGURATION:evidence-i | no tests ran in 0.03s | Check pytest configuration (testpaths, test file naming, col | 2 | 0 | 2026-04-11 |
| CONFIGURATION:idea12-592 | validation.run_quick_validatio | Verify column names in validation.run_quick_validation match | 2 | 0 | 2026-04-13 |
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
| CONFIGURATION:evidence-i | no tests ran in 0.01s | Check pytest configuration (testpaths, collect patterns) and | 1 | 0 | 2026-04-13 |
| DEPENDENCY_ROT:cardioorac | mal_cdf, load_data)
ImportErro | Check if shared is installed: pip install shared | 1 | 0 | 2026-04-13 |
| DEPENDENCY_ROT:registry-f | ============================= | Check the import chain in tests/test_meta.py and install any | 1 | 0 | 2026-04-11 |
| MISSING_FIXTURE:ipd-meta-p | test.py': [Errno 2] No such fi | Restore or regenerate the missing file: t open file  | 1 | 0 | 2026-04-13 |
| MISSING_FIXTURE:ubcma-4230 | newline="",
    )
FileNotFou | Restore or regenerate the missing file: , line 873, in get_h | 1 | 0 | 2026-04-08 |
| SYNTAX_ERROR:ipd-qma-pr | ay(treatment)
    ^
SyntaxErro | Fix the syntax error in the reported file | 1 | 0 | 2026-04-13 |
| TEST_FAILURE:asreview-5 | tiple_raters_fleiss
2 failed, | Read test output and fix failing tests | 1 | 0 | 2026-04-09 |
| TEST_FAILURE:ctgov-sear | est_ci_bounds_valid
20 failed, | Read test output and fix failing tests | 1 | 0 | 2026-04-09 |
| TEST_FAILURE:globalst-5 | truthcert_integrity
4 failed i | Read test output and fix failing tests | 1 | 0 | 2026-04-09 |
| TIMEOUT:advanced-n | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:cardioorac | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-10 |
| TIMEOUT:cbamm-0820 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:cbamm-0820 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:dataextrac | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:dataextrac | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:dta70-4b17 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:dta70-4b17 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:fatiha-pro | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:fatiha-pro | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:grma-paper | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:grma-paper | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:hfn786-583 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:lec-phase0 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-09 |
| TIMEOUT:meta-ecosy | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-10 |
| TIMEOUT:meta-ecosy | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:metaoverfi | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:metaoverfi | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:metasprint | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-09 |
| TIMEOUT:metasprint | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:metasprint | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:mlmresearc | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:mlmresearc | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:nma-a6e8ac | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:nma-a6e8ac | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:nma-c44d8a | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-09 |
| TIMEOUT:prognostic | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-10 |
| TIMEOUT:prognostic | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:pub-bias-s | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-10 |
| TIMEOUT:rmstnma-18 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:rmstnma-18 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:superapp-3 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-09 |
| TIMEOUT:truthcert- | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:truthcert- | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| TIMEOUT:ubcma-4230 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-08 |
| TIMEOUT:ubcma-4230 | timed out | Check for WMI deadlock (Python 3.13), infinite loop, or slow | 1 | 0 | 2026-04-13 |
| UNKNOWN:hta-eviden | no tests ran in 2.35s | Manual investigation needed | 1 | 0 | 2026-04-09 |

## Anti-Recipes (never worked — do NOT retry)

| Recipe | Pattern | Seen | Resolved | Last Seen |
|--------|---------|------|----------|-----------|
| DEPENDENCY_ROT:llm-meta-a | .<9 lines>...
    )
ImportErro | 3 | 0 | 2026-04-13 |
| TEST_FAILURE:metaregres | oderator_regression
16 failed, | 3 | 0 | 2026-04-13 |
