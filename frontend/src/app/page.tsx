"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, categories, Opportunity, User, scheduleLabel } from "../lib/api";
import { Auth, ProfileForm, OpportunityForm, TeamForm } from "./forms";
import { OpportunityDetails, TeamDetails, Dashboard, Admin, NotificationsView } from "./views";
import ActivityFinder from "./finder";

type Page =
  | "explore"
  | "find"
  | "profile"
  | "my-teams"
  | "notifications"
  | "insights"
  | "admin"
  | "create"
  | "opportunity"
  | "team";

export default function Home() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [page, setPage] = useState<Page>("explore");
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [selected, setSelected] = useState<Opportunity | null>(null);
  const [teamId, setTeamId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [error, setError] = useState("");
  const [authOpen, setAuthOpen] = useState(false);
  const [createTeam, setCreateTeam] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [finderQuery, setFinderQuery] = useState("");
  const [showNextStep, setShowNextStep] = useState(false);
  const [pendingAction, setPendingAction] = useState<{
    action: "interest" | "request";
    teamId?: number;
  } | null>(null);
  const [authMessage, setAuthMessage] = useState("");
  const [unread, setUnread] = useState(0);
  const afterLogin = useRef<(() => void) | null>(null);

  const showLocation = useCallback(async () => {
    const params = new URLSearchParams(window.location.search);
    const pages: Page[] = [
      "explore",
      "find",
      "profile",
      "my-teams",
      "notifications",
      "insights",
      "admin",
      "create",
      "opportunity",
      "team",
    ];
    const requested = params.get("page") as Page | null;
    const next = requested && pages.includes(requested) ? requested : "explore";
    const id = Number(params.get("id"));
    if (
      (next === "opportunity" || next === "team") &&
      (!Number.isInteger(id) || id < 1)
    ) {
      setPage("explore");
      return;
    }
    setPage(next);
    setCreateTeam(false);
    if (next === "find") setFinderQuery(params.get("q") || "");
    if (next === "team") setTeamId(id);
    if (next === "opportunity") {
      const search = window.location.search;
      setSelected(null);
      try {
        const item = await api<Opportunity>(`/api/opportunities/${id}`, localStorage.getItem("peerspace_token") || "");
        if (window.location.search === search) {
          setSelected(item);
          setError("");
        }
      } catch (err) {
        if (window.location.search === search)
          setError(
            err instanceof Error ? err.message : "Unable to open activity.",
          );
      }
    }
  }, []);

  function navigate(next: Page, id?: number) {
    const params = new URLSearchParams();
    if (next !== "explore") params.set("page", next);
    if (id) params.set("id", String(id));
    const search = params.toString();
    const index = (window.history.state?.peerSpaceIndex ?? 0) + 1;
    window.history.pushState(
      { peerSpaceIndex: index },
      "",
      search ? `?${search}` : window.location.pathname,
    );
    setShowNextStep(false);
    setPendingAction(null);
    setAuthMessage("");
    void showLocation();
    window.scrollTo(0, 0);
  }

  function goBack() {
    if ((window.history.state?.peerSpaceIndex ?? 0) > 0) window.history.back();
    else navigate("explore");
  }

  function updateFinderQuery(value: string) {
    setFinderQuery(value);
    const params = new URLSearchParams(window.location.search);
    if (value) params.set("q", value);
    else params.delete("q");
    window.history.replaceState(
      window.history.state,
      "",
      `?${params.toString()}`,
    );
  }

  const refresh = useCallback(async () => {
    try {
      const params = new URLSearchParams({ q: query, category, source });
      setOpportunities(
        await api<Opportunity[]>(`/api/opportunities?${params}`, token),
      );
      setError("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load opportunities.",
      );
    }
  }, [query, category, source, token]);

  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    const saved = localStorage.getItem("peerspace_token");
    if (saved)
      api<User>("/api/profile", saved)
        .then((profile) => {
          setToken(saved);
          setUser(profile);
        })
        .catch(() => localStorage.removeItem("peerspace_token"));
  }, []);
  useEffect(() => {
    if (!token) { setUnread(0); return; }
    const update = () => api<{unread_count: number}>("/api/me/notifications", token).then((value) => setUnread(value.unread_count)).catch(() => {});
    void update();
    const timer = window.setInterval(update, 30000);
    return () => window.clearInterval(timer);
  }, [token, page]);

  useEffect(() => {
    if (window.history.state?.peerSpaceIndex == null) {
      window.history.replaceState(
        { ...window.history.state, peerSpaceIndex: 0 },
        "",
        window.location.href,
      );
    }
    void showLocation();
    const handleBack = () => {
      setShowNextStep(false);
      setPendingAction(null);
      void showLocation();
    };
    window.addEventListener("popstate", handleBack);
    return () => window.removeEventListener("popstate", handleBack);
  }, [showLocation]);

  function signIn(value: { token: string; user: User }) {
    localStorage.setItem("peerspace_token", value.token);
    setToken(value.token);
    setUser(value.user);
    setAuthOpen(false);
    void showLocation();
    const next = afterLogin.current;
    afterLogin.current = null;
    if (next) next();
  }
  async function signOut() {
    try {
      await api("/api/auth/logout", token, { method: "POST" });
    } catch {
      /* Local sign-out still succeeds. */
    }
    localStorage.removeItem("peerspace_token");
    setToken("");
    setUser(null);
    navigate("explore");
  }
  function needLogin(action: () => void) {
    if (!user) {
      afterLogin.current = action;
      setAuthOpen(true);
    } else action();
  }
  function openOpportunity(id: number, newlyCreated = false) {
    navigate("opportunity", id);
    if (newlyCreated) setShowNextStep(true);
  }
  function openTeam(id: number) {
    navigate("team", id);
  }
  function loginFor(
    action: "interest" | "request" | "view-team" | "report",
    id?: number,
  ) {
    needLogin(() => {
      if (action === "view-team" && id) openTeam(id);
      else if (action === "interest" || action === "request")
        setPendingAction({ action, teamId: id });
      else setAuthMessage("You’re signed in. Select Report again to continue.");
    });
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <button className="brand" onClick={() => navigate("explore")}>
            <span className="brand-mark">
              p<span>.</span>
            </span>
            <span>
              peer<span className="brand-light">space</span>
              <small>FIND YOUR PEOPLE</small>
            </span>
          </button>
          <nav aria-label="Main navigation">
            <button
              className={page === "explore" ? "active" : ""}
              onClick={() => navigate("explore")}
            >
              Explore
            </button>
            <button
              className={page === "find" ? "active" : ""}
              onClick={() => navigate("find")}
            >Find people</button>
            <button
              className={page === "my-teams" ? "active" : ""}
              onClick={() => needLogin(() => navigate("my-teams"))}
            >
              My teams
            </button>
            <button className={page === "notifications" ? "active" : ""} onClick={() => needLogin(() => navigate("notifications"))}>
              Notifications {unread > 0 && <span className="count-pill">{unread}</span>}
            </button>
            <button
              className={page === "insights" ? "active" : ""}
              onClick={() => needLogin(() => navigate("insights"))}
            >
              Insights
            </button>
            {user?.is_admin && (
              <button
                className={page === "admin" ? "active" : ""}
                onClick={() => navigate("admin")}
              >
                Admin
              </button>
            )}
          </nav>
          <div className="top-actions">
            {user ? (
              <>
                <button
                  className="profile-button"
                  onClick={() => navigate("profile")}
                >
                  <span className="avatar">
                    {user.display_name.charAt(0).toUpperCase()}
                  </span>
                  <span className="profile-name">{user.display_name}</span>
                </button>
                <button className="text-button" onClick={() => void signOut()}>
                  Log out
                </button>
              </>
            ) : (
              <button
                className="button small"
                onClick={() => {
                  afterLogin.current = null;
                  setAuthOpen(true);
                }}
              >
                Log in / Sign up
              </button>
            )}
          </div>
        </div>
      </header>
      {error && (
        <div className="notice error global-notice" role="alert">
          {error}
        </div>
      )}
      {authMessage && (
        <div className="notice success global-notice">{authMessage}</div>
      )}
      {user && !user.profile_complete && page !== "profile" && (
        <div className="profile-alert" role="status">
          <div>
            <strong>Finish your profile</strong>
            <p>Add a short introduction, activity interests and skills before joining or creating a team. Old availability entries are not used as confirmed dates.</p>
          </div>
          <button className="button small" onClick={() => navigate("profile")}>Edit profile →</button>
        </div>
      )}
      {page === "explore" && (
        <main className="container">
          <section className="hero">
            <div>
              <div className="eyebrow">
                <span className="eyebrow-dot" /> MADE FOR DOING THINGS TOGETHER
              </div>
              <h1>
                Good things happen
                <br />
                <em>together.</em>
              </h1>
              <p>
                From hackathons to hikes, find your people and make the plans
                you&apos;ve been thinking about.
              </p>
              <div className="row-actions">
                <button
                  className="button hero-button"
                  onClick={() => navigate("find")}
                >
                  Find people →
                </button>
                <button
                  className="button secondary"
                  onClick={() => navigate("find")}
                >
                  Start something new
                </button>
              </div>
            </div>
            <div className="hero-art" aria-hidden="true">
              <div className="orbit orbit-one" />
              <div className="orbit orbit-two" />
              <div className="art-center">✳</div>
              <div className="art-label label-one">
                new ideas <span>✦</span>
              </div>
              <div className="art-label label-two">
                better together <span>↗</span>
              </div>
              <div className="art-dot dot-one" />
              <div className="art-dot dot-two" />
            </div>
          </section>
          <section className="explore-section">
            <div className="section-heading">
              <div>
                <span className="section-kicker">
                  YOUR NEXT THING STARTS HERE
                </span>
                <h2>
                  Explore opportunities <span className="heading-spark">✳</span>
                </h2>
                <p>
                  Discover something interesting, then find the people to do it
                  with.
                </p>
              </div>
              <span className="result-count">
                {opportunities.length}{" "}
                {opportunities.length === 1 ? "opportunity" : "opportunities"}
              </span>
            </div>
            <div className="filters">
              <label className="search-box">
                <span>⌕</span>
                <input
                  aria-label="Search opportunities"
                  placeholder="Search opportunities..."
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              <select
                aria-label="Filter by category"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
              >
                <option value="">All categories</option>
                {Object.entries(categories).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
              <select
                aria-label="Filter by source"
                value={source}
                onChange={(event) => setSource(event.target.value)}
              >
                <option value="">All sources</option>
                <option value="student">Students</option>
                <option value="curated">Curated</option>
                <option value="scraped">Web</option>
              </select>
            </div>
            <div className="opportunity-grid">
              {opportunities.map((item, index) => (
                <button
                  className="opportunity-card"
                  onClick={() => openOpportunity(item.id)}
                  key={item.id}
                >
                  <div className={`card-art art-${index % 4}`}>
                    <span>{["✳", "✦", "⌁", "↗"][index % 4]}</span>
                    <span className="category-pill">
                      {categories[item.category]}
                    </span>
                  </div>
                  <div className="card-content">
                    <div className="card-meta">
                      {scheduleLabel(item.schedule)} <span>·</span>{" "}
                      {item.source.toUpperCase()}
                    </div>
                    <h3>{item.title}</h3>
                    {item.fit && <p><strong>{item.fit.band} activity fit</strong> · Guidance · {item.fit.explanation.slice(0, 2).join(" · ")}</p>}
                    <p>{item.description}</p>
                    <div className="card-footer">
                      <span>◉ {item.team_count} teams</span>
                      <span>↗ {item.looking_count} looking</span>
                      <b>→</b>
                    </div>
                  </div>
                </button>
              ))}
            </div>
            {!opportunities.length && !error && (
              <div className="empty">
                <span>✳</span>
                <h3>Nothing here just yet</h3>
                <p>
                  Try a different filter, or be the first to create an
                  opportunity.
                </p>
                <button
                  className="button secondary"
                  onClick={() => navigate("find")}
                >
                  Find or create an activity
                </button>
              </div>
            )}
          </section>
          <footer>
            PeerSpace <span>·</span> Made for finding your people.
          </footer>
        </main>
      )}
      {page === "find" && (
        <main className="container inner-page">
          <button className="back" onClick={goBack}>
            ← Back
          </button>
          <ActivityFinder
            query={finderQuery}
            onQuery={updateFinderQuery}
            onOpen={(id) => openOpportunity(id)}
            onCreate={(title) => {
              setNewTitle(title);
              needLogin(() => navigate("create"));
            }}
          />
        </main>
      )}
      {page === "create" && user && (
        <main className="container inner-page">
          <button className="back" onClick={goBack}>
            ← Back
          </button>
          <OpportunityForm
            token={token}
            initialTitle={newTitle}
            onCreated={(id, newlyCreated) => {
              void refresh();
              openOpportunity(id, newlyCreated);
            }}
          />
        </main>
      )}
      {page === "profile" && user && (
        <main className="container inner-page">
          <button className="back" onClick={goBack}>
            ← Back
          </button>
          <ProfileForm user={user} token={token} onSaved={(updated) => {setUser(updated); void refresh();}} />
        </main>
      )}
      {page === "notifications" && user && <main className="container inner-page">
        <NotificationsView token={token} onTeam={openTeam} onOpportunity={openOpportunity} onCount={setUnread} />
      </main>}
      {page === "opportunity" && selected && (
        <main className="container inner-page">
          <button className="back" onClick={goBack}>
            ← Back
          </button>
          <OpportunityDetails
            key={selected.id}
            item={selected}
            token={token}
            user={user}
            onLogin={loginFor}
            onTeam={openTeam}
            onCreateTeam={() => needLogin(() => setCreateTeam(true))}
            onProfile={() => navigate("profile")}
            pendingAction={pendingAction}
            clearPending={() => setPendingAction(null)}
            showNextStep={showNextStep}
            dismissNextStep={() => setShowNextStep(false)}
          />
          {createTeam && (
            <TeamForm
              token={token}
              opportunityId={selected.id}
              onClose={() => setCreateTeam(false)}
              onCreated={(id) => {
                setCreateTeam(false);
                openTeam(id);
              }}
            />
          )}
        </main>
      )}
      {page === "team" && teamId && user && (
        <main className="container inner-page">
          <button className="back" onClick={goBack}>
            ← Back
          </button>
          <TeamDetails teamId={teamId} token={token} user={user} />
        </main>
      )}
      {page === "opportunity" && !selected && !error && (
        <main className="container inner-page">
          <p>Loading activity...</p>
        </main>
      )}
      {(page === "team" ||
        page === "profile" ||
        page === "create" ||
        page === "my-teams" ||
        page === "notifications" ||
        page === "insights") &&
        !user && (
          <main className="container inner-page">
            <div className="panel">
              <h2>Sign in to continue</h2>
              <p>Your place is saved. Sign in to view this page.</p>
              <button className="button" onClick={() => needLogin(() => {})}>
                Log in / Sign up
              </button>
            </div>
          </main>
        )}
      {(page === "my-teams" || page === "insights") && user && (
        <main className="container inner-page">
          <Dashboard mode={page} token={token} onTeam={openTeam} onOpportunity={openOpportunity} />
        </main>
      )}
      {page === "admin" && user?.is_admin && (
        <main className="container inner-page">
          <Admin token={token} />
        </main>
      )}
      {authOpen && (
        <Auth
          onClose={() => {
            afterLogin.current = null;
            setAuthOpen(false);
          }}
          onSuccess={signIn}
        />
      )}
    </div>
  );
}
