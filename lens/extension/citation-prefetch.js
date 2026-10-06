/* One background lookup at a time; visible citations move to the front. */
(() => {
  function create(request) {
    const papers = new Map(),
      matches = new Map(),
      references = new Map(),
      queue = [];
    let running = false;
    function pump() {
      if (running || !queue.length) return;
      const job = queue.shift();
      running = true;
      job.started = true;
      Promise.resolve()
        .then(() => request(job.path, job.body))
        .then(
          (data) => {
            // A temporary model warning must not become a permanent hover result.
            if (
              ((job.cache === matches && typeof data.match !== "number") ||
                (job.cache === references && data.state === "unavailable")) &&
              job.cache.get(job.id) === job
            )
              job.cache.delete(job.id);
            job.resolve(data);
          },
          (error) => {
            if (job.cache.get(job.id) === job) job.cache.delete(job.id);
            job.reject(error);
            if (error.offline) {
              for (const waiting of queue.splice(0)) {
                if (waiting.cache.get(waiting.id) === waiting)
                  waiting.cache.delete(waiting.id);
                waiting.reject(error);
              }
            }
          },
        )
        .finally(() => {
          running = false;
          setTimeout(pump, 0);
        });
    }
    function get(cache, id, route, priority, body) {
      let job = cache.get(id);
      if (!job) {
        job = {
          cache,
          id,
          path: body ? route : `${route}?id=${encodeURIComponent(id)}`,
          body,
          started: false,
        };
        job.promise = new Promise((resolve, reject) => {
          job.resolve = resolve;
          job.reject = reject;
        });
        cache.set(id, job);
        queue.push(job);
      }
      if (priority && !job.started) {
        const index = queue.indexOf(job);
        if (index >= 0) {
          queue.splice(index, 1);
          queue.unshift(job);
        }
      }
      pump();
      return job.promise;
    }
    const paper = (id, priority = true) =>
      get(papers, id, "/api/paper", priority);
    const match = (id, priority = true) =>
      get(matches, id, "/api/paper-match", priority);
    return {
      paper,
      match,
      resolve(citation, priority = true) {
        const details = citation.details || {};
        const body = {
          reference: citation.reference.slice(0, 3000),
          title: (details.title || "").slice(0, 500),
          authors: (details.authors || "").slice(0, 500),
          year: String(details.year || "").slice(0, 4),
          doi: (details.doi || "").slice(0, 200),
        };
        return get(
          references,
          citation.reference,
          "/api/resolve-reference",
          priority,
          body,
        );
      },
      warm(ids) {
        for (const id of new Set(ids)) {
          paper(id, false).catch(() => {});
          match(id, false).catch(() => {});
        }
      },
      invalidate() {
        matches.clear();
        for (let i = queue.length - 1; i >= 0; i--)
          if (queue[i].cache === matches) {
            const [job] = queue.splice(i, 1);
            job.reject(new Error("Citation scores are refreshing."));
          }
      },
    };
  }
  globalThis.LensCitationPrefetch = { create };
})();
