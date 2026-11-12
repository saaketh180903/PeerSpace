export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type User = {
  id: number;
  display_name: string;
  email: string;
  skills: Record<string, number>;
  interests: string[];
  availability: string[];
  available_dates: string[];
  courses: string[];
  experience: string[];
  contact: string | null;
  is_admin: boolean;
};
export type Opportunity = {
  id: number;
  title: string;
  description: string;
  category: string;
  source: string;
  organizer: string | null;
  official_url: string | null;
  event_date: string | null;
  team_count: number;
  looking_count: number;
};
export type Team = {
  id: number;
  opportunity_id: number;
  owner_id: number;
  name: string;
  capacity: number;
  member_count: number;
  skills: Record<string, number>;
  availability: string[];
  group_link?: string | null;
  members?: (User & { contact: string | null })[];
  score?: number;
  explanation?: string[];
};
export type JoinRequest = {
  id: number;
  status: string;
  team_id?: number;
  team_name?: string;
  opportunity_id?: number;
  user?: User;
  match?: { score: number; explanation: string[] } | null;
};
export type Participation = {
  looking: boolean;
  team: { id: number; name: string } | null;
  requests: {
    id: number;
    team_id: number;
    team_name: string;
    status: string;
  }[];
};
export type TeamOptions = {
  teams: Team[];
  total_teams: number;
  full_count: number;
  hidden_count: number;
  hidden_reasons: string[];
  already_joined: boolean;
};
export type Message = {
  id: number;
  author: string;
  text: string;
  created_at: string;
};
export type Candidate = { user: User; score: number; explanation: string[] };
export type Insight = {
  period: string;
  demand: Record<string, number>;
  team_fill: { members: number; capacity: number; rate: number | null };
  time_to_join: { sample_size: number; average_seconds: number | null };
  missing_skills: Record<string, number>;
};

export const categories: Record<string, string> = {
  hackathon: "Hackathons",
  course_project: "Course projects",
  study_group: "Study groups",
  trek_sport: "Treks & sports",
};

export class ApiError extends Error {
  detail: unknown;
  constructor(message: string, detail: unknown) {
    super(message);
    this.detail = detail;
  }
}

export async function api<T>(
  path: string,
  token = "",
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = result.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message || "Something went wrong. Please try again.";
    throw new ApiError(message, detail);
  }
  return result as T;
}

export const csv = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
export function skillsFromText(value: string): Record<string, number> {
  const result: Record<string, number> = {};
  for (const item of csv(value)) {
    const [name, level] = item.split(":").map((part) => part.trim());
    if (
      !name ||
      !level ||
      !Number.isInteger(Number(level)) ||
      Number(level) < 1 ||
      Number(level) > 5
    )
      throw new Error("Write skills as Python:4, Design:3 (levels 1–5).");
    result[name] = Number(level);
  }
  return result;
}
export const skillsText = (skills: Record<string, number>) =>
  Object.entries(skills)
    .map(([name, level]) => `${name}:${level}`)
    .join(", ");
