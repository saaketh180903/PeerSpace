"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  api,
  Candidate,
  categories,
  Insight,
  JoinRequest,
  Message,
  Opportunity,
  Participation,
  DateAnswers,
  scheduleLabel,
  Team,
  TeamOptions,
  User,
  Notification,
  MyParticipation,
  Invitation,
  Schedule,
} from "../lib/api";
import {ScheduleEditor} from "./forms";

const weekdayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function DateAnswerFields({schedule, value, onChange}: {schedule: Schedule; value: DateAnswers; onChange: (value: DateAnswers) => void}) {
  const [selected, setSelected] = useState("");
  if (!schedule?.kind || schedule.kind === "undecided") return <p>Dates can be decided with the team later.</p>;
  const required = new Set(schedule.required_dates || []);
  function toggleDate(day: string) {
    onChange({...value, dates: value.dates.includes(day) ? value.dates.filter((item) => item !== day) : [...value.dates, day].sort()});
  }
  return <div className="date-answer-fields">
    <p><strong>When can you take part?</strong> Required dates are marked below.</p>
    {schedule.kind === "single" && schedule.start_date && <label className="date-choice">
      <input type="checkbox" checked={value.dates.includes(schedule.start_date)} onChange={() => toggleDate(schedule.start_date!)} />
      {schedule.start_date} {required.has(schedule.start_date) && <span className="required-tag">Required</span>}
    </label>}
    {schedule.kind === "range" && <>
      {(schedule.required_dates || []).map((day) => <label className="date-choice" key={day}>
        <input type="checkbox" checked={value.dates.includes(day)} onChange={() => toggleDate(day)} />{day}<span className="required-tag">Required</span>
      </label>)}
      <div className="date-picker-row"><label>Other dates you can attend
        <input type="date" min={schedule.start_date || undefined} max={schedule.end_date || undefined} value={selected} onChange={(event) => setSelected(event.target.value)} />
      </label><button type="button" className="button secondary small" disabled={!selected || value.dates.includes(selected)} onClick={() => {toggleDate(selected); setSelected("");}}>Add date</button></div>
      {value.dates.filter((day) => !required.has(day)).length > 0 && <div className="selected-dates">{value.dates.filter((day) => !required.has(day)).map((day) => <button type="button" className="date-chip" key={day} onClick={() => toggleDate(day)}>{day} ×</button>)}</div>}
    </>}
    {schedule.kind === "recurring" && <div className="weekday-choices">
      {(schedule.weekdays || []).map((day) => <label className="date-choice" key={day}>
        <input type="checkbox" checked={value.weekdays.includes(day)} onChange={(event) => onChange({...value, weekdays: event.target.checked ? [...value.weekdays, day] : value.weekdays.filter((item) => item !== day)})} />
        {weekdayNames[day]} {(schedule.required_weekdays || []).includes(day) && <span className="required-tag">Required</span>}
      </label>)}
    </div>}
    {schedule.time_window && <p>Suggested time: {schedule.time_window}</p>}
  </div>;
}

export function OpportunityDetails({
  item,
  token,
  user,
  onLogin,
  onTeam,
  onCreateTeam,
  onProfile,
  pendingAction,
  clearPending,
  showNextStep,
  dismissNextStep,
}: {
  item: Opportunity;
  token: string;
  user: User | null;
  onLogin: (
    action: "interest" | "request" | "view-team" | "report",
    teamId?: number,
  ) => void;
  onTeam: (id: number) => void;
  onCreateTeam: () => void;
  onProfile: () => void;
  pendingAction: { action: "interest" | "request"; teamId?: number } | null;
  clearPending: () => void;
  showNextStep: boolean;
  dismissNextStep: () => void;
}) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [recommended, setRecommended] = useState<Team[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [lookingCount, setLookingCount] = useState(item.looking_count);
  const [participation, setParticipation] = useState<Participation | null>(
    null,
  );
  const [options, setOptions] = useState<TeamOptions | null>(null);
  const [busy, setBusy] = useState(false);
  const [action, setAction] = useState<{kind: "interest" | "request"; team?: Team} | null>(null);
  const [answers, setAnswers] = useState<DateAnswers>({dates: [], weekdays: []});
  const [motivation, setMotivation] = useState("");
  const [questionAnswer, setQuestionAnswer] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    try {
      setTeams(await api<Team[]>(`/api/opportunities/${item.id}/teams`));
      if (token) {
        const [nextOptions, nextParticipation] = await Promise.all([
          api<TeamOptions>(`/api/opportunities/${item.id}/team-options`, token),
          api<Participation>(
            `/api/opportunities/${item.id}/participation`,
            token,
          ),
        ]);
        setOptions(nextOptions);
        setParticipation(nextParticipation);
        setRecommended(nextOptions.teams);
      } else {
        setOptions(null);
        setParticipation(null);
        setRecommended([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load teams.");
    } finally {
      setLoading(false);
    }
  }, [item.id, token]);
  useEffect(() => {
    void load();
  }, [load]);
  async function interest() {
    if (!user) return onLogin("interest");
    try {
      setBusy(true);
      setError("");
      await api(`/api/opportunities/${item.id}/interest`, token, {
        method: "POST",
        body: JSON.stringify({date_answers: answers}),
      });
      setLookingCount(
        (await api<Opportunity>(`/api/opportunities/${item.id}`)).looking_count,
      );
      setMessage(
        "You’re in the looking pool! Team owners can find your profile.",
      );
      clearPending();
      dismissNextStep();
      await load();
      setAction(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save interest.");
    } finally {
      setBusy(false);
    }
  }
  async function withdraw() {
    if (!user) return onLogin("interest");
    try {
      await api(`/api/opportunities/${item.id}/interest`, token, {
        method: "DELETE",
      });
      setLookingCount(
        (await api<Opportunity>(`/api/opportunities/${item.id}`)).looking_count,
      );
      setMessage("You left the looking pool.");
      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not update interest.",
      );
    }
  }
  async function request(teamId: number) {
    if (!user) return onLogin("request", teamId);
    try {
      setBusy(true);
      setError("");
      await api(`/api/teams/${teamId}/requests`, token, { method: "POST", body: JSON.stringify({date_answers: answers, motivation, question_answer: questionAnswer}) });
      setMessage("Request sent. Check Notifications or My teams for the owner's decision.");
      clearPending();
      await load();
      setAction(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send request.");
      await load();
    } finally {
      setBusy(false);
    }
  }
  async function report() {
    if (!user) return onLogin("report");
    const reason = window.prompt("Why are you reporting this opportunity?");
    if (!reason?.trim()) return;
    try {
      await api("/api/reports", token, {
        method: "POST",
        body: JSON.stringify({
          target_type: "opportunity",
          target_id: item.id,
          reason,
        }),
      });
      setMessage("Report submitted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit report.");
    }
  }
  return (
    <>
      <section className="detail-header">
        <div>
          <span className="section-kicker">
            {categories[item.category]} · {item.source}
          </span>
          <h1>{item.title}</h1>
          <p>{item.description}</p>
          <div className="detail-meta">
            <span>{scheduleLabel(item.schedule)}</span>
            <span>♧ {lookingCount} looking</span>
            {item.organizer && <span>By {item.organizer}</span>}
            {item.eligibility && <span>Organizer eligibility: {item.eligibility} (not verified by PeerSpace)</span>}
            {item.official_url && (
              <a href={item.official_url} target="_blank" rel="noreferrer">
                Official link ↗
              </a>
            )}
            <button className="inline-link" onClick={() => void report()}>
              Report
            </button>
            {user && participation?.looking && (
              <>
                <button className="inline-link" onClick={() => {setAnswers(participation.date_answers || {dates: [], weekdays: []}); setAction({kind: "interest"});}}>Edit your dates</button>
                <button className="inline-link" onClick={() => void withdraw()}>Leave looking pool</button>
              </>
            )}
          </div>
        </div>
        <div className="detail-actions">
          {participation?.team ? (
            <button
              className="button"
              onClick={() => onTeam(participation.team!.id)}
            >
              Open your team
            </button>
          ) : (
            <>
              <button
                className="button"
                disabled={
                  busy || !!participation?.looking || (!!user && !participation)
                }
                onClick={() => user ? setAction({kind: "interest"}) : onLogin("interest")}
              >
                {participation?.looking
                  ? "You’re in the looking pool"
                  : "I’m looking for a team"}
              </button>
              <button
                className="button secondary"
                disabled={!!user && !participation}
                onClick={onCreateTeam}
              >
                + Create a team
              </button>
            </>
          )}
        </div>
      </section>
      {message && <div className="notice success">{message}</div>}
      {error && <div className="notice error">{error}</div>}
      {user && item.fit && <section className="fit-panel" aria-label="Activity fit">
        <div>
          <span className="fit-badge">{item.fit.band} activity fit</span>
          <p>Guidance based on your profile. It does not include activity dates.</p>
        </div>
        <ul className="fit-reasons">{item.fit.explanation.map((reason) => <li key={reason}>{reason}</li>)}</ul>
        {item.fit.band !== "High" && <button className="inline-link" onClick={onProfile}>Improve your match → Edit profile</button>}
      </section>}
      {action && <section className="panel participation-panel">
        <h2>{action.kind === "interest" ? "Join the looking pool" : `Request to join ${action.team?.name}`}</h2>
        <p>{scheduleLabel(action.team?.schedule || item.schedule)}</p>
        <DateAnswerFields schedule={action.team?.schedule || item.schedule} value={answers} onChange={setAnswers} />
        {action.kind === "request" && <>
          <label>Why would you like to join?<textarea value={motivation} onChange={(event) => setMotivation(event.target.value)} /></label>
          {action.team?.question && <label>{action.team.question}<textarea required value={questionAnswer} onChange={(event) => setQuestionAnswer(event.target.value)} /></label>}
        </>}
        <div className="row-actions"><button className="button" disabled={busy || (!!action.team?.question && !questionAnswer.trim())} onClick={() => action.kind === "interest" ? void interest() : void request(action.team!.id)}>Confirm {action.kind === "interest" ? "looking" : "request"}</button>
          <button className="button secondary" onClick={() => setAction(null)}>Cancel</button></div>
      </section>}
      {item.official_url && (
        <p className="activity-note">
          PeerSpace helps you find people. Register for the event separately
          using its official link.
        </p>
      )}
      {participation?.team && (
        <div className="status-card">
          <div><strong>You are a member of {participation.team.name}</strong>
            <p>Your team workspace is ready. You can join one team for this activity at a time.</p>
          </div>
          <button className="button small" onClick={() => onTeam(participation.team!.id)}>Open your team →</button>
        </div>
      )}
      {!!participation?.requests.length && (
        <section className="request-summary" aria-label="Your requests">
          <strong>Your requests</strong>
          {participation.requests.map((request) => (
            <div className="request-row" key={request.id}>
              <button
                className="inline-link"
                onClick={() => onTeam(request.team_id)}
              >
                {request.team_name}
              </button>
              <span className="count-pill">{request.status}</span>
            </div>
          ))}
        </section>
      )}
      {pendingAction && user && (
        <div className="notice confirmation" role="status">
          {pendingAction.action === "request" &&
          (!options || !participation) ? (
            <p>Checking whether the team is still available...</p>
          ) : pendingAction.action === "request" &&
            participation?.requests.some(
              (request) => request.team_id === pendingAction.teamId && request.status !== "closed",
            ) ? (
            <p>
              You have already requested this team. See your request status
              below.
            </p>
          ) : pendingAction.action === "request" &&
            !recommended.some((team) => team.id === pendingAction.teamId) ? (
            <p>
              This team is no longer available to request. Check your profile
              and the team requirements below.
            </p>
          ) : (
            <>
              <p>
                {pendingAction.action === "interest"
                  ? "Ready to join the looking pool?"
                  : `Ready to request ${recommended.find((team) => team.id === pendingAction.teamId)?.name || "this team"}?`}{" "}
                Nothing has been submitted yet.
              </p>
              <button
                className="button small"
                disabled={
                  busy ||
                  (pendingAction.action === "interest" && !!participation?.team)
                }
                onClick={() =>
                  pendingAction.action === "interest"
                    ? (setAction({kind: "interest"}), clearPending())
                    : pendingAction.teamId && (setAction({kind: "request", team: recommended.find((team) => team.id === pendingAction.teamId)}), clearPending())
                }
              >
                {pendingAction.action === "interest"
                  ? "Confirm interest"
                  : "Confirm request"}
              </button>{" "}
            </>
          )}
          <button className="button secondary small" onClick={clearPending}>
            Cancel
          </button>
        </div>
      )}
      {showNextStep && !participation?.team && (
        <section className="panel next-step">
          <span className="section-kicker">YOUR ACTIVITY IS READY</span>
          <h2>What would you like to do next?</h2>
          <p>Create the first team, join the looking pool, or return later.</p>
          <div className="row-actions">
            <button
              className="button"
              onClick={() => {
                dismissNextStep();
                onCreateTeam();
              }}
            >
              Create the first team
            </button>
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => setAction({kind: "interest"})}
            >
              Join the looking pool
            </button>
            <button className="button secondary" onClick={dismissNextStep}>
              Do this later
            </button>
          </div>
        </section>
      )}
      <div className="section-heading compact">
        <div>
          <span className="section-kicker">FIND YOUR PEOPLE</span>
          <h2>{participation?.team ? "Your team is ready" : user ? "Find a team" : "Open teams"}</h2>
          <p>
            {participation?.team
              ? "Open your team to meet members, review updates and coordinate."
              : user
                ? "Teams are ranked using your profile and activity-specific date answers."
                : "Sign in to see team-fit guidance and request to join."}
          </p>
        </div>
      </div>
      {user && !participation?.team && <p className="recommendation-note">Team fit is guidance. Confirm required dates before you request to join.</p>}
      {loading && <p>Loading teams...</p>}
      <div className="team-list">
        {(user
          ? recommended
          : teams.filter((team) => team.member_count < team.capacity)
        ).map((team) => {
          const previous = participation?.requests.find(
            (request) => request.team_id === team.id,
          );
          return (
            <article className="team-card" key={team.id}>
              <div>
                <div className="team-title">
                  <h3>{team.name}</h3>
                  <span className="count-pill">
                    {team.member_count} / {team.capacity} members
                  </span>
                </div>
                <p>
                  {team.skills.length
                    ? `Looking for ${team.skills.join(", ")}`
                    : "Open to people who want to join."}
                </p>
                {team.explanation && (
                  <div className="match-explanation">
                    <strong>
                      {team.band} team fit · Guidance, not a guarantee
                    </strong>{" "}
                    · {team.explanation.join(" · ")}
                  </div>
                )}
              </div>
              <div className="row-actions">
                <button
                  className="button secondary small"
                  onClick={() =>
                    user ? onTeam(team.id) : onLogin("view-team", team.id)
                  }
                >
                  View team
                </button>
                <button
                  className="button small"
                  disabled={busy || (!!previous && previous.status !== "closed")}
                  onClick={() => user ? (setAnswers(participation?.date_answers?.dates ? participation.date_answers : {dates: [], weekdays: []}), setAction({kind: "request", team})) : onLogin("request", team.id)}
                >
                  {previous && previous.status !== "closed" ? `Request ${previous.status}` : "Request to join"}
                </button>
              </div>
            </article>
          );
        })}
      </div>
      {!loading &&
        !error &&
        !(
          user
            ? recommended
            : teams.filter((team) => team.member_count < team.capacity)
        ).length &&
        !participation?.team && (
          <div className="empty small-empty">
            <span>✳</span>
            <h3>
              {options?.hidden_count
                ? "No teams match your required details"
                : "No open teams yet"}
            </h3>
            <p>
              {options?.hidden_count
                ? "Some teams are hidden by the requirements above. Update your profile, join the looking pool, or start a team."
                : "Join the looking pool or create the first team for this activity."}
            </p>
          </div>
        )}
    </>
  );
}

export function TeamDetails({
  teamId,
  token,
  user,
}: {
  teamId: number;
  token: string;
  user: User;
}) {
  const [team, setTeam] = useState<Team | null>(null);
  const [requests, setRequests] = useState<JoinRequest[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editingSchedule, setEditingSchedule] = useState(false);
  const load = useCallback(async () => {
    try {
      const value = await api<Team>(`/api/teams/${teamId}`, token);
      setTeam(value);
      if (value.members)
        setMessages(
          await api<Message[]>(`/api/teams/${teamId}/messages`, token),
        );
      if (value.owner_id === user.id) {
        setRequests(
          await api<JoinRequest[]>(`/api/teams/${teamId}/requests`, token),
        );
        setCandidates(
          await api<Candidate[]>(`/api/teams/${teamId}/candidates`, token),
        );
      }
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load team.");
    }
  }, [teamId, token, user.id]);
  useEffect(() => {
    void load();
  }, [load]);
  async function decide(id: number, decision: string) {
    try {
      await api(`/api/requests/${id}/${decision}`, token, { method: "POST" });
      setNotice(`Request ${decision === "approve" ? "approved" : "declined"}.`);
      await load();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not update request.",
      );
    }
  }
  async function teamAction(path: string, body?: object) {
    if (!window.confirm("Confirm this team change?")) return;
    try {
      await api(`/api/teams/${teamId}/${path}`, token, {method: "POST", ...(body ? {body: JSON.stringify(body)} : {})});
      setNotice("Team updated.");
      await load();
    } catch (err) {setError(err instanceof Error ? err.message : "Could not update team.");}
  }
  async function invite(userId: number) {
    if (!window.confirm("Send this student an invitation?")) return;
    try {
      await api(`/api/teams/${teamId}/invitations?candidate_id=${userId}`, token, {method: "POST"});
      setNotice("Invitation sent.");
      await load();
    } catch (err) {setError(err instanceof Error ? err.message : "Could not invite student.");}
  }
  async function send(event: FormEvent) {
    event.preventDefault();
    try {
      await api(`/api/teams/${teamId}/messages`, token, {
        method: "POST",
        body: JSON.stringify({ text }),
      });
      setText("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send message.");
    }
  }
  async function reportPerson(id: number) {
    const reason = window.prompt("Why are you reporting this profile?");
    if (!reason?.trim()) return;
    try {
      await api("/api/reports", token, {
        method: "POST",
        body: JSON.stringify({ target_type: "profile", target_id: id, reason }),
      });
      setNotice("Report submitted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit report.");
    }
  }
  if (!team) return <div className="panel">{error || "Loading team..."}</div>;
  return (
    <>
      <section className="detail-header">
        <div>
          <span className="section-kicker">{categories[team.category]} · {team.activity_title}</span>
          <h1>{team.name}</h1>
          <p>{team.goal}</p>
          <p>{scheduleLabel(team.schedule)}</p>
          <p>
            {team.member_count} of {team.capacity} members ·{" "}
            {team.member_count >= team.capacity
              ? "Team full"
              : `${team.capacity - team.member_count} spots open`}
          </p>
        </div>
        <div className="count-badge">
          {team.member_count}
          <span>/ {team.capacity}</span>
        </div>
      </section>
      {error && <div className="notice error">{error}</div>}
      {notice && <div className="notice success">{notice}</div>}
      {team.members && !team.closed && <div className="panel">
        {team.owner_id === user.id ? <>
          <h2>Manage team</h2>
          <p>Update plans or manage members below. To leave as owner, transfer ownership to a member or close the team.</p>
          <button className="button secondary small" onClick={() => setEditingSchedule(!editingSchedule)}>Update schedule</button>{" "}
          <button className="button secondary small" onClick={() => void teamAction("close")}>Close team</button>
          {editingSchedule && <ScheduleChange teamId={teamId} token={token} initial={team.schedule} onSaved={() => {setEditingSchedule(false); void load();}} />}
        </> : <>
          <h2>Membership</h2>
          <button className="button secondary small" onClick={() => void teamAction("leave", {return_to_pool: false})}>Leave team</button>{" "}
          <button className="button secondary small" onClick={() => void teamAction("leave", {return_to_pool: true})}>Leave and return to looking pool</button>
        </>}
      </div>}
      <div className="detail-columns">
        <div>
          <section className="panel">
            <span className="section-kicker">THE PEOPLE</span>
            <h2>Team members</h2>
            {team.members ? (
              team.members.map((person) => (
                <div className="person-row" key={person.id}>
                  <span className="avatar">
                    {person.display_name.charAt(0).toUpperCase()}
                  </span>
                  <div>
                    <strong>
                      {person.display_name}
                      {person.id === team.owner_id ? " · Owner" : ""}
                    </strong>
                    <p>{person.contact || "No contact shared"}</p>
                    {team.owner_id === user.id && person.id !== user.id && <div className="row-actions">
                      <button className="inline-link" onClick={() => void teamAction(`remove/${person.id}`)}>Remove member</button>
                      <button className="inline-link" onClick={() => void teamAction("transfer", {user_id: person.id})}>Make owner</button>
                    </div>}
                  </div>
                </div>
              ))
            ) : (
              <p>Member contact details are available after you join.</p>
            )}
            {team.group_link && (
              <a
                href={team.group_link}
                target="_blank"
                rel="noreferrer"
                className="inline-link"
              >
                Open team group ↗
              </a>
            )}
          </section>
          {team.owner_id === user.id && (
            <section className="panel applicant-panel">
              <span className="section-kicker">YOUR TEAM</span>
              <h2>Join requests</h2>
              {requests.length ? (
                requests.map((request) => (
                  <div className="applicant-card" key={request.id}>
                    <div className="applicant-heading">
                      <div><strong>{request.user?.display_name}</strong><span className="count-pill">{request.status}</span></div>
                      {request.match && <span className="fit-badge">{request.match.score}% team match</span>}
                    </div>
                    <p className="applicant-bio">{request.user?.bio || "Profile introduction not yet added."}</p>
                    <div className="applicant-facts">
                      <span><small>Skills</small>{request.user?.skills.join(", ") || "Not listed"}</span>
                      <span><small>Interests</small>{request.user?.interests.map((name) => categories[name] || name).join(", ") || "Not listed"}</span>
                      <span><small>Courses</small>{request.user?.courses.join(", ") || "Not listed"}</span>
                      <span><small>Experience</small>{request.user?.experience.join(", ") || "Not listed"}</span>
                      <span><small>Dates they can attend</small>{request.date_answers?.dates?.join(", ") || "Not confirmed"}</span>
                      <span><small>Recurring days</small>{request.date_answers?.weekdays?.map((day) => ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day]).join(", ") || "Not confirmed"}</span>
                    </div>
                    <p><strong>Motivation:</strong> {request.motivation || "No answer"}</p>
                    {team.question && <p><strong>{team.question}</strong> {request.question_answer || "No answer"}</p>}
                    {request.match && <div className="factor-report"><strong>Why this score?</strong><ul>{request.match.explanation.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>}
                    {request.match?.date_status === "not_confirmed" && <p className="notice">Dates must be confirmed before approval.</p>}
                    {request.status === "pending" && <div className="row-actions">
                      <button className="button small" onClick={() => void decide(request.id, "approve")}>Approve</button>
                      <button className="button secondary small" onClick={() => void decide(request.id, "decline")}>Decline</button>
                    </div>}
                  </div>
                ))
              ) : (
                <p>No requests yet.</p>
              )}
              <h3 className="subheading">People looking</h3>
              {candidates.length ? (
                candidates.map((candidate) => (
                  <div className="candidate applicant-card" key={candidate.user.id}>
                    <div className="applicant-heading"><strong>{candidate.user.display_name}</strong>
                      {candidate.user.bio && candidate.user.skills.length ? <span className="fit-badge">{candidate.score}% team match</span> : <span className="count-pill">Profile needs an update</span>}
                    </div>
                    <p className="applicant-bio">{candidate.user.bio || "This student has not updated their introduction."}</p>
                    <div className="applicant-facts">
                      <span><small>Skills</small>{candidate.user.skills.join(", ") || "Not listed"}</span>
                      <span><small>Dates</small>{candidate.date_answers?.dates?.join(", ") || "Not confirmed"}</span>
                    </div>
                    {candidate.user.bio && <div className="factor-report"><strong>Match factors</strong><ul>{candidate.explanation.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>}
                    <div className="row-actions"><button className="button small" onClick={() => void invite(candidate.user.id)}>Invite</button>
                      <button className="inline-link" onClick={() => void reportPerson(candidate.user.id)}>Report profile</button></div>
                  </div>
                ))
              ) : (
                <p>No matching people in the looking pool yet.</p>
              )}
            </section>
          )}
        </div>
        <section className="panel">
          <span className="section-kicker">KEEP IN TOUCH</span>
          <h2>Team conversation</h2>
          {team.members ? (
            <>
              <div className="messages">
                {messages.length ? (
                  messages.map((message) => (
                    <div className="message" key={message.id}>
                      <strong>{message.author}</strong>
                      <small>
                        {new Date(message.created_at).toLocaleString()}
                      </small>
                      <p>{message.text}</p>
                    </div>
                  ))
                ) : (
                  <p>No messages yet. Say hello!</p>
                )}
              </div>
              <form className="message-form" onSubmit={send}>
                <input
                  required
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder="Write a message..."
                />
                <button className="button small" type="submit">
                  Send →
                </button>
              </form>
            </>
          ) : (
            <p>The conversation is private to accepted team members.</p>
          )}
        </section>
      </div>
    </>
  );
}

function ScheduleChange({teamId, token, initial, onSaved}: {teamId: number; token: string; initial: Schedule; onSaved: () => void}) {
  const [schedule, setSchedule] = useState<Schedule>(initial);
  const [error, setError] = useState("");
  async function save() {
    try {
      await api(`/api/teams/${teamId}/schedule`, token, {method: "PUT", body: JSON.stringify(schedule)});
      onSaved();
    } catch (err) {setError(err instanceof Error ? err.message : "Could not save schedule.");}
  }
  return <div><ScheduleEditor value={schedule} onChange={setSchedule} />
    {error && <div className="notice error">{error}</div>}
    <button className="button small" onClick={() => void save()}>Save schedule</button>
  </div>;
}

export function NotificationsView({token, onTeam, onOpportunity, onCount}: {
  token: string; onTeam: (id: number) => void; onOpportunity: (id: number) => void; onCount: (count: number) => void;
}) {
  const [items, setItems] = useState<Notification[]>([]);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const result = await api<{unread_count: number; items: Notification[]}>("/api/me/notifications", token);
      setItems(result.items); onCount(result.unread_count);
    } catch (err) {setError(err instanceof Error ? err.message : "Could not load notifications.");}
  }, [token, onCount]);
  useEffect(() => {void load();}, [load]);
  async function open(item: Notification) {
    if (!item.read) await api(`/api/me/notifications/${item.id}/read`, token, {method: "POST"});
    await load();
    if (item.team_id) onTeam(item.team_id);
    else if (item.opportunity_id) onOpportunity(item.opportunity_id);
  }
  return <><span className="section-kicker">UPDATES</span><h1>Notifications</h1>
    {error && <div className="notice error">{error}</div>}
    <section className="panel">{items.length ? items.map((item) => <button className="team-card clickable" key={item.id} onClick={() => void open(item)}>
      <strong>{item.read ? "" : "● "}{item.text}</strong>
      <span>{item.activity_title} · {categories[item.category || ""] || item.category} · {scheduleLabel(item.schedule)}</span>
    </button>) : <p>No updates yet.</p>}</section>
  </>;
}

type Report = {
  id: number;
  target_type: "profile" | "opportunity";
  target_id: number;
  reason: string;
  status: string;
};
export function Admin({ token }: { token: string }) {
  const [reports, setReports] = useState<Report[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    try {
      setReports(await api<Report[]>("/api/admin/reports", token));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load reports.");
    }
  }, [token]);
  useEffect(() => {
    void load();
  }, [load]);
  async function act(action: string, id: number) {
    try {
      await api(`/api/admin/${action}/${id}`, token, { method: "POST" });
      setMessage("Action recorded.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not apply action.");
    }
  }
  return (
    <>
      <span className="section-kicker">COMMUNITY SAFETY</span>
      <h1>Reports</h1>
      <p className="page-intro">
        Review reports and hide content or suspend accounts when necessary.
      </p>
      {error && <div className="notice error">{error}</div>}
      {message && <div className="notice success">{message}</div>}
      <section className="panel">
        {reports.length ? (
          reports.map((report) => (
            <div className="request-row" key={report.id}>
              <div>
                <strong>
                  {report.target_type} #{report.target_id} · {report.status}
                </strong>
                <p>{report.reason}</p>
              </div>
              <div className="row-actions">
                <button
                  className="button secondary small"
                  onClick={() =>
                    void act(
                      report.target_type === "profile"
                        ? "hide-profile"
                        : "hide-opportunity",
                      report.target_id,
                    )
                  }
                >
                  Hide
                </button>
                {report.target_type === "profile" && (
                  <button
                    className="button small"
                    onClick={() => void act("suspend-user", report.target_id)}
                  >
                    Suspend
                  </button>
                )}
              </div>
            </div>
          ))
        ) : (
          <p>No reports yet.</p>
        )}
      </section>
    </>
  );
}

export function Dashboard({
  mode,
  token,
  onTeam,
  onOpportunity,
}: {
  mode: "my-teams" | "insights";
  token: string;
  onTeam: (id: number) => void;
  onOpportunity: (id: number) => void;
}) {
  const [participation, setParticipation] = useState<MyParticipation | null>(null);
  const [insights, setInsights] = useState<Insight | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    async function load() {
      try {
        if (mode === "my-teams") {
          setParticipation(await api<MyParticipation>("/api/me/participation", token));
        } else setInsights(await api<Insight>("/api/insights", token));
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Could not load this page.",
        );
      }
    }
    void load();
  }, [mode, token]);
  async function decideInvite(id: number, decision: "accept" | "decline") {
    if (!window.confirm(`${decision === "accept" ? "Join" : "Decline"} this team invitation?`)) return;
    try {
      await api(`/api/invitations/${id}/${decision}`, token, {method: "POST"});
      setParticipation(await api<MyParticipation>("/api/me/participation", token));
    } catch (err) {setError(err instanceof Error ? err.message : "Could not update invitation.");}
  }
  if (mode === "my-teams") {
    type Group = {title: string; category: string; schedule: Schedule; teams: Team[]; requests: JoinRequest[]; looking: boolean; invitations: Invitation[]};
    const groups = new Map<number, Group>();
    function activity(id: number, title: string, category: string, schedule: Schedule) {
      if (!groups.has(id)) groups.set(id, {title, category, schedule, teams: [], requests: [], looking: false, invitations: []});
      return groups.get(id)!;
    }
    participation?.teams.forEach((team) => activity(team.opportunity_id, team.activity_title, team.category, team.schedule).teams.push(team));
    participation?.requests.forEach((request) => {
      if (request.opportunity_id) activity(request.opportunity_id, request.activity_title || "Activity", request.category || "", request.schedule || {kind: "undecided"}).requests.push(request);
    });
    participation?.looking.forEach((item) => {activity(item.opportunity_id, item.activity_title, item.category, item.schedule).looking = true;});
    participation?.invitations.forEach((invite) => {
      if (invite.opportunity_id) activity(invite.opportunity_id, invite.activity_title || "Activity", invite.category || "", invite.schedule || {kind: "undecided"}).invitations.push(invite);
    });
    return <>
      <span className="section-kicker">YOUR PEOPLE</span><h1>My teams</h1>
      <p className="page-intro">Your membership, requests, looking pools and invitations by activity.</p>
      {error && <div className="notice error">{error}</div>}
      {!participation && !error && <p>Loading your activities...</p>}
      {participation && !groups.size && <div className="empty small-empty"><h3>No activities yet</h3><p>Find an activity in Explore and join a team or its looking pool.</p></div>}
      {Array.from(groups.entries()).map(([id, group]) => <section className="panel" key={id}>
        <span className="section-kicker">{categories[group.category] || group.category}</span>
        <h2><button className="inline-link" onClick={() => onOpportunity(id)}>{group.title}</button></h2>
        <p>{scheduleLabel(group.schedule)}</p>
        {group.teams.map((team) => <div className="request-row" key={team.id}>
          <button className="inline-link" onClick={() => onTeam(team.id)}>Member of {team.name} →</button>
          <span>{team.member_count}/{team.capacity} members · {scheduleLabel(team.schedule)}</span>
        </div>)}
        {group.looking && <div className="request-row"><button className="inline-link" onClick={() => onOpportunity(id)}>Looking for a team · Update dates →</button></div>}
        {group.requests.map((request) => <div className="request-row" key={request.id}>
          <button className="inline-link" onClick={() => request.team_id && onTeam(request.team_id)}>Request to {request.team_name} →</button>
          <span className="count-pill">{request.status}</span>
        </div>)}
        {group.invitations.map((invite) => <div className="request-row" key={invite.id}>
          <button className="inline-link" onClick={() => onTeam(invite.team_id)}>Invitation from {invite.team_name} →</button>
          <span className="count-pill">{invite.status}</span>
          {invite.status === "pending" && <div className="row-actions">
            <button className="button small" onClick={() => void decideInvite(invite.id, "accept")}>Accept</button>
            <button className="button secondary small" onClick={() => void decideInvite(invite.id, "decline")}>Decline</button>
          </div>}
        </div>)}
      </section>)}
    </>;
  }
  return (
    <>
      <span className="section-kicker">A LOOK AT THE COMMUNITY</span>
      <h1>Insights</h1>
      <p className="page-intro">
        A snapshot of activity across PeerSpace. These numbers reflect the data
        currently in the app. When present, [DEMO] profiles and teams are
        included in these figures and do not represent real participation.
      </p>
      {error && <div className="notice error">{error}</div>}
      {insights && (
        <>
          <div className="stats-grid">
            <div className="stat">
              <span>TEAM FILL RATE</span>
              <strong>
                {insights.team_fill.rate === null
                  ? "—"
                  : `${Math.round(insights.team_fill.rate * 100)}%`}
              </strong>
              <small>
                {insights.team_fill.members} members /{" "}
                {insights.team_fill.capacity} places
              </small>
            </div>
            <div className="stat">
              <span>AVG. TIME TO JOIN</span>
              <strong>
                {insights.time_to_join.average_seconds === null
                  ? "—"
                  : `${Math.round(insights.time_to_join.average_seconds / 3600)}h`}
              </strong>
              <small>
                {insights.time_to_join.sample_size} completed journeys
              </small>
            </div>
            <div className="stat">
              <span>PEOPLE INTERESTED</span>
              <strong>
                {Object.values(insights.demand).reduce((sum, n) => sum + n, 0)}
              </strong>
              <small>Category interests, not unique users</small>
            </div>
          </div>
          <div className="detail-columns">
            <section className="panel">
              <h2>Interest by category</h2>
              {Object.entries(insights.demand).length ? (
                Object.entries(insights.demand).map(([category, count]) => (
                  <div className="request-row" key={category}>
                    <span>{categories[category]}</span>
                    <strong>{count}</strong>
                  </div>
                ))
              ) : (
                <p>No interest recorded yet.</p>
              )}
            </section>
            <section className="panel">
              <h2>Skills teams are looking for</h2>
              {Object.entries(insights.missing_skills).length ? (
                Object.entries(insights.missing_skills).map(
                  ([skill, count]) => (
                    <div className="request-row" key={skill}>
                      <span>{skill}</span>
                      <strong>{count}</strong>
                    </div>
                  ),
                )
              ) : (
                <p>No skill requirements recorded yet.</p>
              )}
            </section>
          </div>
        </>
      )}
    </>
  );
}
