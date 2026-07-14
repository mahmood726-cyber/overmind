"""Re-measurement harness for the arm gate (Part V Fix #2) — reproducibility artifact.

Runs the group_code-required arm binding over real AACT outcomes measured across >=2
arms (the selection-error setup) and PRINTS accept/block RATE statistics (sensitivity,
specificity, the wrong-arm false-accept tail). Its output is internal measurement
metrics about the gate, not a trial/effect world-claim — hence listed in the ratchet.

Run: PYTHONPATH=. python overmind/gates/measure_arm_gate.py
"""
import duckdb, random
from overmind.gates.resolver import default_resolver, Resolution
from overmind.gates.channel import ExportChannel, ChannelViolation
from overmind.gates.contract import Claim, SourceTier

AACT=r"C:\Projects\cochrane-vs-registry\aact.duckdb"
con=duckdb.connect(AACT, read_only=True)
rows = con.execute("""
WITH multi AS (
  SELECT outcome_id FROM outcome_measurements
  WHERE ctgov_group_code IS NOT NULL AND param_value_num IS NOT NULL
  GROUP BY outcome_id HAVING COUNT(DISTINCT ctgov_group_code) >= 2
),
sib AS (
  SELECT om.id AS om_id,
         MIN(CASE WHEN s.ctgov_group_code<>om.ctgov_group_code THEN s.ctgov_group_code END) AS sib_group
  FROM outcome_measurements om JOIN multi ON multi.outcome_id=om.outcome_id
  JOIN outcome_measurements s ON s.outcome_id=om.outcome_id
  GROUP BY om.id
)
SELECT om.id, om.nct_id, om.param_value_num, om.title, om.ctgov_group_code, om.units,
       o.time_frame, rg.title AS arm_title, sib.sib_group,
       rg2.title AS sib_arm
FROM outcome_measurements om
JOIN multi ON multi.outcome_id=om.outcome_id
JOIN sib ON sib.om_id=om.id
LEFT JOIN outcomes o ON o.id=om.outcome_id
LEFT JOIN result_groups rg ON rg.id=om.result_group_id
LEFT JOIN result_groups rg2 ON rg2.nct_id=om.nct_id AND rg2.ctgov_group_code=sib.sib_group
WHERE om.ctgov_group_code IS NOT NULL AND om.param_value_num IS NOT NULL AND sib.sib_group IS NOT NULL
LIMIT 6000
""").fetchall()
random.seed(0); random.shuffle(rows); rows=rows[:2500]
print(f"sampled real AACT om rows across >=2 arms (with sibling): {len(rows)}")

ch=ExportChannel(); legacy=ExportChannel(require_group_code=False)  # default resolver

def gt_of(nct,val,title,group,units,tf,arm):
    return Resolution(True, True, "aact",
        ground_truth={"value":val,"title":title,"group":group,"arm":arm,"timepoint":tf,"unit":units})

sens_ok=sens_n=spec_block=spec_n=title_ref=title_n=0
legacy_fa=legacy_n=0
for (om_id,nct,val,title,group,units,tf,arm,sib,sib_arm) in rows:
    res=gt_of(nct,val,title,group,units,tf,arm)
    base=dict(outcome=title or "", timepoint=(tf or "n/a"), unit=(units or "n/a"))
    loc=f"{nct}#om[{om_id}]"
    # CORRECT group_code
    sens_n+=1
    try: ch._guard_semantic(Claim(title or "x",val,SourceTier.REGISTRY,loc,meta={**base,"group_code":group}),res); sens_ok+=1
    except ChannelViolation: pass
    # WRONG sibling group_code
    spec_n+=1
    try: ch._guard_semantic(Claim(title or "x",val,SourceTier.REGISTRY,loc,meta={**base,"group_code":sib}),res)
    except ChannelViolation: spec_block+=1
    # TITLE-ONLY under default -> should refuse
    if arm:
        title_n+=1
        try: ch._guard_semantic(Claim(title or "x",val,SourceTier.REGISTRY,loc,meta={**base,"arm":arm}),res)
        except ChannelViolation: title_ref+=1
        # LEGACY title heuristic false-accept with WRONG sibling arm title
        if sib_arm and sib_arm!=arm:
            legacy_n+=1
            try: legacy._guard_semantic(Claim(title or "x",val,SourceTier.REGISTRY,loc,meta={**base,"arm":sib_arm}),res); legacy_fa+=1
            except ChannelViolation: pass

def pct(a,b): return 100*a/b if b else float('nan')
print("\n=== NEW gate: group_code REQUIRED (default) ===")
print(f"  sensitivity (correct group_code ACCEPTED):     {sens_ok}/{sens_n} = {pct(sens_ok,sens_n):.3f}%")
print(f"  specificity (wrong sibling group_code BLOCKED): {spec_block}/{spec_n} = {pct(spec_block,spec_n):.3f}%")
print(f"  wrong-arm FALSE-ACCEPT tail (NEW):              {spec_n-spec_block}/{spec_n} = {pct(spec_n-spec_block,spec_n):.3f}%")
print(f"  title-only now REFUSED (arm-UNVERIFIED):        {title_ref}/{title_n} = {pct(title_ref,title_n):.3f}%")
print("\n=== OLD title heuristic (require_group_code=False) ===")
print(f"  wrong-arm-TITLE FALSE-ACCEPT (the tail we closed): {legacy_fa}/{legacy_n} = {pct(legacy_fa,legacy_n):.3f}%")
