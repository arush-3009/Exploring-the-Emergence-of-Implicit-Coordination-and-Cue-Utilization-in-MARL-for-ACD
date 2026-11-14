# Ordinary work

[file_requests.py](file_requests.py) is the ordinary traffic of the two zones. Every interval
the same set of requests is made, and each one succeeds or fails depending on the state of
the two servers it runs between. `workload_config.toml` in the world folder sets how many
requests each route carries per interval, and
[workload_config.template.toml](workload_config.template.toml) lists the key.

Twelve requests run every interval in every world.

| Route | Requests per interval |
|---|---|
| EA to A1, A2, A3 | 1 each |
| EB to B1, B2, B3 | 1 each |
| A1 to B1, A2 to B2, A3 to B3 | 1 each |
| B1 to A1, B2 to A2, B3 to A3 | 1 each |

A request succeeds when neither end is isolated, the target's file service is running, and,
when the source is a server, its service is running too. Whether a server is infected makes no
difference to its requests. So a request fails when one of its servers is isolated or stopped,
which is what Isolate, Restore and an outage do to a server.

`run_file_requests()` evaluates the whole batch after the interval's actions and attacks and
stores the results. Each defender sees the latest result of its zone's employee's requests and of
its servers' requests to their partners, as a success or failure flag.
