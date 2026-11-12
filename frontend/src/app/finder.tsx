"use client";

import { useEffect, useState } from "react";
import { api, categories, Opportunity } from "../lib/api";

export default function ActivityFinder({
  query,
  onQuery,
  onOpen,
  onCreate,
}: {
  query: string;
  onQuery: (value: string) => void;
  onOpen: (id: number) => void;
  onCreate: (title: string) => void;
}) {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({ q: query, suggest: "true" });
        const result = await api<Opportunity[]>(
          `/api/opportunities?${params}`,
          "",
          { signal: controller.signal },
        );
        setItems(result);
        setError("");
      } catch (err) {
        if (!controller.signal.aborted)
          setError(
            err instanceof Error ? err.message : "Could not search activities.",
          );
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 200);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  return (
    <section className="finder">
      <span className="section-kicker">FIND YOUR PEOPLE</span>
      <h1>What do you want to do?</h1>
      <p>
        Search for an existing event or activity. You can join a team or start
        your own once you choose one.
      </p>
      <label className="search-box finder-search">
        <span aria-hidden="true">⌕</span>
        <input
          autoFocus
          aria-label="Search activities"
          placeholder="Search a hackathon, course, activity..."
          value={query}
          onChange={(event) => onQuery(event.target.value)}
        />
      </label>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      <div className="finder-heading">
        <h2>{query.trim() ? "Possible matches" : "Choose an activity"}</h2>
        <span className="result-count">
          {loading ? "Searching..." : `${items.length} found`}
        </span>
      </div>
      <div className="team-list">
        {items.map((item) => (
          <button
            className="team-card clickable"
            key={item.id}
            onClick={() => onOpen(item.id)}
          >
            <div>
              <span className="section-kicker">
                {categories[item.category]} · {item.source}
              </span>
              <h3>{item.title}</h3>
              <p>
                {item.event_date || "See date details"} · {item.team_count}{" "}
                {item.team_count === 1 ? "team" : "teams"} ·{" "}
                {item.looking_count} looking
              </p>
            </div>
            <span>View activity →</span>
          </button>
        ))}
      </div>
      {!loading && !error && !items.length && (
        <div className="empty small-empty">
          <span>✳</span>
          <h3>No activities found</h3>
          <p>Try a different name, or create the activity you have in mind.</p>
        </div>
      )}
      <div className="finder-create">
        <div>
          <h3>Can’t find what you’re looking for?</h3>
          <p>
            Create a new activity for a hackathon, study group, walk, or
            anything else you want to do together.
          </p>
        </div>
        <button
          className="button secondary"
          onClick={() => onCreate(query.trim())}
        >
          + Create a new activity
        </button>
      </div>
    </section>
  );
}
