"use client";

import { FormEvent, useState } from "react";
import {
  api,
  ApiError,
  categories,
  csv,
  Opportunity,
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
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      onSuccess(
        await api<{ token: string; user: User }>(
          `/api/auth/${signup ? "signup" : "login"}`,
          "",
          {
            method: "POST",
            body: JSON.stringify({
              email,
              password,
              ...(signup ? { display_name: name } : {}),
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
  const [skills, setSkills] = useState(skillsText(user.skills));
  const [interests, setInterests] = useState(user.interests.join(", "));
  const [availability, setAvailability] = useState(
    user.availability.join(", "),
  );
  const [dates, setDates] = useState(user.available_dates.join(", "));
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
          skills: skillsFromText(skills),
          interests: csv(interests),
          availability: csv(availability),
          available_dates: csv(dates),
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
        Your skills and availability help us show relevant teams. Contact
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
        <label>
          Skills and levels <small>For example: Python:4, Design:3</small>
          <input
            value={skills}
            onChange={(event) => setSkills(event.target.value)}
            placeholder="Python:4, Design:3"
          />
        </label>
        <div className="form-grid">
          <label>
            Interests <small>Comma separated</small>
            <input
              value={interests}
              onChange={(event) => setInterests(event.target.value)}
              placeholder="hackathon, study_group"
            />
          </label>
          <label>
            Regular availability <small>Comma separated</small>
            <input
              value={availability}
              onChange={(event) => setAvailability(event.target.value)}
              placeholder="evenings, weekends"
            />
          </label>
          <label>
            Available dates <small>YYYY-MM-DD, comma separated</small>
            <input
              value={dates}
              onChange={(event) => setDates(event.target.value)}
              placeholder="2026-11-28"
            />
          </label>
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
  const [date, setDate] = useState("");
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
          event_date: date || null,
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
            Event date <small>Optional</small>
            <input
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
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
  const [availability, setAvailability] = useState("");
  const [required, setRequired] = useState(false);
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
            availability: csv(availability),
            availability_required: required,
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
          Skills needed <small>e.g. Python:4, Design:3</small>
          <input
            value={skills}
            onChange={(event) => setSkills(event.target.value)}
          />
        </label>
        <label>
          Availability <small>Comma separated</small>
          <input
            value={availability}
            onChange={(event) => setAvailability(event.target.value)}
            placeholder="evenings, weekends"
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={required}
            onChange={(event) => setRequired(event.target.checked)}
          />{" "}
          Matching availability is required
        </label>
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
