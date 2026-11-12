"use client";

import { FormEvent, useState } from "react";
import {
  api,
  ApiError,
  categories,
  csv,
  Opportunity,
  Schedule,
  skillsFromText,
  skillsText,
  User,
} from "../lib/api";

function Modal({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        onClick={(event) => event.stopPropagation()}
      >
        <button className="close" onClick={onClose} aria-label="Close">
          ×
        </button>
        {children}
      </div>
    </div>
  );
}

export function Auth({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: (value: { token: string; user: User }) => void;
}) {
  const [signup, setSignup] = useState(true);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [bio, setBio] = useState("");
  const [skills, setSkills] = useState("");
  const [interests, setInterests] = useState<string[]>([]);
  const [topics, setTopics] = useState("");
  const [courses, setCourses] = useState("");
  const [experience, setExperience] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      if (signup && !interests.length) throw new Error("Choose at least one activity interest.");
      onSuccess(
        await api<{ token: string; user: User }>(
          `/api/auth/${signup ? "signup" : "login"}`,
          "",
          {
            method: "POST",
            body: JSON.stringify({
              email,
              password,
              ...(signup ? { display_name: name, bio, skills: csv(skills), interests, topics: csv(topics), courses: csv(courses), experience: csv(experience) } : {}),
            }),
          },
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Please try again.");
    }
  }
  return (
    <Modal onClose={onClose}>
      <span className="section-kicker">WELCOME TO PEERSPACE</span>
      <h2>{signup ? "Let’s find your people." : "Welcome back."}</h2>
      <p>
        {signup
          ? "Create an account and find your next adventure."
          : "Log in to pick up where you left off."}
      </p>
      <form onSubmit={submit} className="form-stack">
        {signup && (
          <label>
            Name
            <input
              required
              maxLength={120}
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Your name"
            />
          </label>
        )}
        <label>
          Email
          <input
            required
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
          />
        </label>
        <label>
          Password
          <input
            required
            type="password"
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="At least 8 characters"
          />
        </label>
        {signup && <>
          <label>Short introduction
            <textarea required minLength={20} maxLength={500} value={bio} onChange={(event) => setBio(event.target.value)} placeholder="What do you enjoy working on?" />
          </label>
          <label>Skills <small>Comma separated names, no levels</small>
            <input required value={skills} onChange={(event) => setSkills(event.target.value)} placeholder="Python, design, hiking" />
          </label>
          <fieldset className="interest-choices"><legend>Activities you are interested in</legend>
            {Object.entries(categories).map(([key, label]) => <label key={key} className="check">
              <input type="checkbox" checked={interests.includes(key)} onChange={(event) => setInterests(event.target.checked ? [...interests, key] : interests.filter((value) => value !== key))} /> {label}
            </label>)}
          </fieldset>
          <label>Topics you like <small>Optional</small><input value={topics} onChange={(event) => setTopics(event.target.value)} placeholder="AI, design, mountains" /></label>
          <label>Courses <small>Optional</small><input value={courses} onChange={(event) => setCourses(event.target.value)} placeholder="CS101, EE101" /></label>
          <label>Past projects or experience <small>Optional</small><input value={experience} onChange={(event) => setExperience(event.target.value)} placeholder="Web app, hiking" /></label>
          <div className="notice">Profile preview: {name || "Your name"} · {csv(skills).join(", ") || "Add a skill"} · {interests.map((value) => categories[value]).join(", ") || "Choose an activity"}<p>{bio}</p></div>
        </>}
        {error && (
          <div className="notice error" role="alert">
            {error}
          </div>
        )}
        <button className="button" type="submit">
          {signup ? "Create account" : "Log in"} →
        </button>
      </form>
      <p className="switch-text">
        {signup ? "Already have an account?" : "New here?"}{" "}
        <button
          className="inline-link"
          onClick={() => {
            setSignup(!signup);
            setError("");
          }}
        >
          {signup ? "Log in" : "Sign up"}
        </button>
      </p>
    </Modal>
  );
}

export function ProfileForm({
  user,
  token,
  onSaved,
}: {
  user: User;
  token: string;
  onSaved: (user: User) => void;
}) {
  const [name, setName] = useState(user.display_name);
  const [bio, setBio] = useState(user.bio || "");
  const [skills, setSkills] = useState(skillsText(user.skills));
  const [interests, setInterests] = useState(user.interests.join(", "));
  const [topics, setTopics] = useState((user.topics || []).join(", "));
  const [courses, setCourses] = useState(user.courses.join(", "));
  const [experience, setExperience] = useState(user.experience.join(", "));
  const [contact, setContact] = useState(user.contact || "");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const updated = await api<User>("/api/profile", token, {
        method: "PUT",
        body: JSON.stringify({
          display_name: name,
          bio,
          skills: skillsFromText(skills),
          interests: csv(interests),
          topics: csv(topics),
          courses: csv(courses),
          experience: csv(experience),
          contact: contact || null,
        }),
      });
      onSaved(updated);
      setMessage("Profile saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save profile.");
    }
  }
  return (
    <section className="panel wide-form">
      <span className="section-kicker">A LITTLE ABOUT YOU</span>
      <h1>Your profile</h1>
      <p>
        Your interests, skills and experience help us show relevant teams. Contact
        details are visible only to your team members.
      </p>
      <form className="form-stack" onSubmit={submit}>
        <label>
          Display name
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label>Short introduction
          <textarea required minLength={20} maxLength={500} value={bio} onChange={(event) => setBio(event.target.value)} />
        </label>
        <label>
          Skills <small>Comma separated names</small>
          <input
            required
            value={skills}
            onChange={(event) => setSkills(event.target.value)}
            placeholder="Python, Design"
          />
        </label>
        <div className="form-grid">
          <fieldset className="interest-choices"><legend>Activity interests</legend>
            {Object.entries(categories).map(([key, label]) => <label key={key} className="check">
              <input type="checkbox" checked={csv(interests).includes(key)} onChange={(event) => setInterests(event.target.checked ? [...csv(interests), key].join(", ") : csv(interests).filter((value) => value !== key).join(", "))} /> {label}
            </label>)}
          </fieldset>
          <label>Topics you like <small>Comma separated</small><input value={topics} onChange={(event) => setTopics(event.target.value)} placeholder="AI, design, mountains" /></label>
          <label>
            Courses <small>Comma separated</small>
            <input
              value={courses}
              onChange={(event) => setCourses(event.target.value)}
              placeholder="CS101, EE101"
            />
          </label>
          <label>
            Experience <small>Comma separated</small>
            <input
              value={experience}
              onChange={(event) => setExperience(event.target.value)}
              placeholder="hiking, beginner"
            />
          </label>
          <label>
            Contact <small>Only shared with your team</small>
            <input
              value={contact}
              onChange={(event) => setContact(event.target.value)}
              placeholder="Email or other contact"
            />
          </label>
        </div>
        {error && <div className="notice error">{error}</div>}
        {message && <div className="notice success">{message}</div>}
        <button className="button" type="submit">
          Save profile →
        </button>
      </form>
    </section>
  );
}

export function ScheduleEditor({value, onChange}: {value: Schedule; onChange: (value: Schedule) => void}) {
  const update = (part: Partial<Schedule>) => onChange({...value, ...part});
  return <fieldset className="schedule-editor">
    <legend>Schedule</legend>
    <label>When?
      <select value={value.kind} onChange={(event) => update({kind: event.target.value as Schedule["kind"]})}>
        <option value="undecided">To be decided together</option>
        <option value="single">One date</option>
        <option value="range">Date range</option>
        <option value="recurring">Recurring weekdays in a date range</option>
      </select>
    </label>
    {value.kind !== "undecided" && <label>Start date
      <input required type="date" value={value.start_date || ""} onChange={(event) => update({start_date: event.target.value, ...(value.kind === "single" && (value.required_dates || []).length ? {required_dates: [event.target.value]} : {})})} />
    </label>}
    {(value.kind === "range" || value.kind === "recurring") && <label>End date
      <input required type="date" value={value.end_date || ""} onChange={(event) => update({end_date: event.target.value})} />
    </label>}
    {value.kind === "single" && <label className="check">
      <input type="checkbox" checked={(value.required_dates || []).includes(value.start_date || "")} onChange={(event) => update({required_dates: event.target.checked && value.start_date ? [value.start_date] : []})} />
      This date is required
    </label>}
    {value.kind === "range" && <label>Required dates <small>YYYY-MM-DD, comma separated. Other dates are preferences.</small>
      <input value={(value.required_dates || []).join(", ")} onChange={(event) => update({required_dates: csv(event.target.value)})} />
    </label>}
    {value.kind === "recurring" && <>
      <p>Meeting days</p>
      {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, index) => <label className="check" key={day}>
        <input type="checkbox" checked={(value.weekdays || []).includes(index)} onChange={(event) => update({weekdays: event.target.checked ? [...(value.weekdays || []), index] : (value.weekdays || []).filter((item) => item !== index)})} /> {day}
      </label>)}
      <p>Required days</p>
      {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, index) => <label className="check" key={day}>
        <input type="checkbox" checked={(value.required_weekdays || []).includes(index)} onChange={(event) => update({required_weekdays: event.target.checked ? [...(value.required_weekdays || []), index] : (value.required_weekdays || []).filter((item) => item !== index)})} /> {day}
      </label>)}
    </>}
    {value.kind !== "undecided" && <label>Time window <small>Optional, for example 10:00–13:00</small>
      <input value={value.time_window || ""} onChange={(event) => update({time_window: event.target.value})} />
    </label>}
  </fieldset>;
}

export function OpportunityForm({
  token,
  onCreated,
  initialTitle = "",
}: {
  token: string;
  onCreated: (id: number, newlyCreated: boolean) => void;
  initialTitle?: string;
}) {
  const [title, setTitle] = useState(initialTitle);
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("hackathon");
  const [schedule, setSchedule] = useState<Schedule>({kind: "undecided"});
  const [topics, setTopics] = useState("");
  const [skills, setSkills] = useState("");
  const [course, setCourse] = useState("");
  const [experience, setExperience] = useState("");
  const [eligibility, setEligibility] = useState("");
  const [organizer, setOrganizer] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [similar, setSimilar] = useState<Opportunity[]>([]);
  const [duplicateId, setDuplicateId] = useState<number | null>(null);
  async function submit(event: FormEvent, confirm = false) {
    event.preventDefault();
    setError("");
    setSimilar([]);
    setDuplicateId(null);
    try {
      const item = await api<{ id: number }>("/api/opportunities", token, {
        method: "POST",
        body: JSON.stringify({
          title,
          description,
          category,
          schedule,
          topics: csv(topics),
          skills: csv(skills),
          course: course || null,
          experience: csv(experience),
          eligibility,
          organizer: organizer || null,
          official_url: url || null,
          confirm_similar: confirm,
        }),
      });
      onCreated(item.id, true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not create opportunity.",
      );
      if (
        err instanceof ApiError &&
        err.detail &&
        typeof err.detail === "object"
      ) {
        const detail = err.detail as {
          similar?: Opportunity[];
          existing_id?: number;
        };
        setSimilar(detail.similar || []);
        setDuplicateId(detail.existing_id || null);
      }
    }
  }
  return (
    <section className="panel wide-form">
      <span className="section-kicker">BRING PEOPLE TOGETHER</span>
      <h1>Create an opportunity</h1>
      <p>
        Share something you want to do. Others can find it, show interest, and
        form teams.
      </p>
      <form className="form-stack" onSubmit={submit}>
        <label>
          Title
          <input
            required
            maxLength={200}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. Weekend design jam"
          />
        </label>
        <label>
          What is it about?
          <textarea
            required
            rows={4}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Tell people what you have in mind..."
          />
        </label>
        <div className="form-grid">
          <label>
            Category
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              {Object.entries(categories).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Organizer <small>Optional</small>
            <input
              value={organizer}
              onChange={(event) => setOrganizer(event.target.value)}
            />
          </label>
          <label>
            Official link <small>Optional</small>
            <input
              type="url"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://"
            />
          </label>
        </div>
        <ScheduleEditor value={schedule} onChange={setSchedule} />
        <div className="form-grid">
          <label>Topics <small>Comma separated</small><input value={topics} onChange={(event) => setTopics(event.target.value)} placeholder="AI, sustainability" /></label>
          <label>Suggested skills <small>Comma separated</small><input value={skills} onChange={(event) => setSkills(event.target.value)} placeholder="Python, Design" /></label>
          <label>Course <small>Optional</small><input value={course} onChange={(event) => setCourse(event.target.value)} /></label>
          <label>Relevant experience <small>Comma separated</small><input value={experience} onChange={(event) => setExperience(event.target.value)} /></label>
        </div>
        <label>Organizer eligibility <small>Shown as supplied; PeerSpace does not verify it.</small>
          <textarea value={eligibility} onChange={(event) => setEligibility(event.target.value)} />
        </label>
        {error && (
          <div className="notice error">
            {error}
            {duplicateId && (
              <p>
                <button
                  type="button"
                  className="inline-link"
                  onClick={() => onCreated(duplicateId, false)}
                >
                  Open existing opportunity →
                </button>
              </p>
            )}
            {similar.length > 0 && (
              <div>
                <p>
                  Possible matches:{" "}
                  {similar.map((item) => (
                    <button
                      type="button"
                      className="inline-link"
                      key={item.id}
                      onClick={() => onCreated(item.id, false)}
                    >
                      {item.title} →{" "}
                    </button>
                  ))}
                </p>
                <button
                  type="button"
                  className="inline-link"
                  onClick={(event) => void submit(event, true)}
                >
                  Create anyway
                </button>
              </div>
            )}
          </div>
        )}
        <button className="button" type="submit">
          Publish opportunity →
        </button>
      </form>
    </section>
  );
}

export function TeamForm({
  token,
  opportunityId,
  onClose,
  onCreated,
}: {
  token: string;
  opportunityId: number;
  onClose: () => void;
  onCreated: (id: number) => void;
}) {
  const [name, setName] = useState("");
  const [capacity, setCapacity] = useState(4);
  const [skills, setSkills] = useState("");
  const [goal, setGoal] = useState("");
  const [schedule, setSchedule] = useState<Schedule>({kind: "undecided"});
  const [question, setQuestion] = useState("");
  const [course, setCourse] = useState("");
  const [experience, setExperience] = useState("");
  const [link, setLink] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const team = await api<{ id: number }>(
        `/api/opportunities/${opportunityId}/teams`,
        token,
        {
          method: "POST",
          body: JSON.stringify({
            name,
            capacity,
            skills: skillsFromText(skills),
            goal,
            schedule,
            question,
            course: course || null,
            experience: csv(experience),
            group_link: link || null,
          }),
        },
      );
      onCreated(team.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create team.");
    }
  }
  return (
    <Modal onClose={onClose}>
      <span className="section-kicker">START SOMETHING</span>
      <h2>Create a team</h2>
      <p>You&apos;ll be the owner and count toward the team size.</p>
      <form className="form-stack" onSubmit={submit}>
        <label>
          Team name
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label>
          Team size
          <input
            type="number"
            min={1}
            max={100}
            value={capacity}
            onChange={(event) => setCapacity(Number(event.target.value))}
          />
        </label>
        <label>
          Skills needed <small>Comma separated names</small>
          <input
            value={skills}
            onChange={(event) => setSkills(event.target.value)}
          />
        </label>
        <label>Team goal<textarea value={goal} onChange={(event) => setGoal(event.target.value)} placeholder="What will this team work toward?" /></label>
        <ScheduleEditor value={schedule} onChange={setSchedule} />
        <label>Optional question for applicants<input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What would you contribute?" /></label>
        <label>
          Course <small>Optional</small>
          <input
            value={course}
            onChange={(event) => setCourse(event.target.value)}
          />
        </label>
        <label>
          Experience <small>Comma separated</small>
          <input
            value={experience}
            onChange={(event) => setExperience(event.target.value)}
          />
        </label>
        <label>
          External group link <small>Only members can see it</small>
          <input
            type="url"
            value={link}
            onChange={(event) => setLink(event.target.value)}
          />
        </label>
        {error && <div className="notice error">{error}</div>}
        <button className="button" type="submit">
          Create team →
        </button>
      </form>
    </Modal>
  );
}
