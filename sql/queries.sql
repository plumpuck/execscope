-- Average cost per algorithm in one experiment (the "leaderboard").
-- :exp is the experiment id.
SELECT label,
       COUNT(*)                    AS n_parents,
       AVG(vs_vwap_bps)            AS avg_vs_vwap_bps,
       AVG(vs_arrival_bps)         AS avg_vs_arrival_bps,
       AVG(is_total_bps)           AS avg_is_bps,
       AVG(filled_qty / target_qty) AS fill_rate
FROM runs
WHERE experiment_id = :exp
GROUP BY label
ORDER BY avg_vs_vwap_bps;

-- Paired difference of every algorithm against the one-shot baseline, parent by parent.
SELECT a.label,
       AVG(a.vs_vwap_bps - b.vs_vwap_bps)                         AS mean_diff_bps,
       SUM(CASE WHEN a.vs_vwap_bps < b.vs_vwap_bps THEN 1 ELSE 0 END) AS parents_where_better,
       COUNT(*)                                                    AS n
FROM runs a
JOIN runs b ON b.experiment_id = a.experiment_id AND b.parent = a.parent AND b.label = 'oneshot'
WHERE a.experiment_id = :exp AND a.label <> 'oneshot'
GROUP BY a.label;

-- Worst 5 parent orders for one algorithm.
SELECT parent, start_ts, vs_vwap_bps, is_total_bps
FROM runs
WHERE experiment_id = :exp AND label = :label
ORDER BY vs_vwap_bps DESC
LIMIT 5;
