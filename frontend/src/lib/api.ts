export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
export type Schedule = {
  kind: "undecided" | "single" | "range" | "recurring";
  start_date?: string | null; end_date?: string | null;
  weekdays?: number[]; required_dates?: string[]; required_weekdays?: number[];
  time_window?: string;
};
export type DateAnswers = {dates: string[]; weekdays: number[]};
export type Fit = {score: number; band: string; explanation: string[]; date_status?: string; missing_required_dates?: string[]; breakdown?: {factor: string; matched: number; weight: number}[]};
export type User = {
  id: number; display_name: string; email: string; bio: string; skills: string[];
  interests: string[]; topics: string[]; courses: string[]; experience: string[];
  contact: string | null; is_admin: boolean; profile_complete: boolean;
};
export type Opportunity = {
  id: number; title: string; description: string; category: string; source: string;
  organizer: string | null; official_url: string | null; event_date: string | null;
  topics: string[]; skills: string[]; course: string | null; experience: string[];
  eligibility: string; schedule: Schedule; fit?: Fit;
  team_count: number; looking_count: number;
};
export type Team = {
  id: number; opportunity_id: number; owner_id: number; name: string;
  activity_title: string; category: string; goal: string; schedule: Schedule;
  question: string; closed: boolean; capacity: number; member_count: number;
  skills: string[]; course?: string | null; experience?: string[];
  group_link?: string | null; members?: (User & {contact: string | null})[];
  score?: number; band?: string; date_status?: string; explanation?: string[];
};
export type JoinRequest = {
  id: number; status: string; team_id?: number; team_name?: string;
  opportunity_id?: number; activity_title?: string; category?: string;
  schedule?: Schedule; user?: User; match?: Fit | null;
  date_answers?: DateAnswers; motivation?: string; question_answer?: string;
};
export type Invitation = {id: number; status: string; team_id: number; team_name: string; opportunity_id?: number; activity_title?: string; category?: string; schedule?: Schedule};
export type Participation = {
  looking: boolean; date_answers: DateAnswers;
  team: {id: number; name: string} | null;
  requests: {id: number; team_id: number; team_name: string; status: string}[];
  invitations: Invitation[];
};
export type TeamOptions = {teams: Team[]; total_teams: number; full_count: number; hidden_count: number; hidden_reasons: string[]; already_joined: boolean};
export type Message = {id: number; author: string; text: string; created_at: string};
export type Candidate = {user: User; score: number; band: string; explanation: string[]; date_answers: DateAnswers; date_status: string};
export type Notification = {id: number; text: string; read: boolean; team_id: number | null; opportunity_id: number | null; activity_title: string | null; category: string | null; schedule: Schedule};
export type MyParticipation = {teams: Team[]; requests: JoinRequest[]; looking: {opportunity_id: number; activity_title: string; category: string; schedule: Schedule; date_answers: DateAnswers}[]; invitations: Invitation[]};
export type Insight = {
  period: string; demand: Record<string, number>;
  team_fill: {members: number; capacity: number; rate: number | null};
  time_to_join: {sample_size: number; average_seconds: number | null};
  missing_skills: Record<string, number>;
};
export const categories: Record<string, string> = {
  hackathon: "Hackathons", course_project: "Course projects",
  study_group: "Study groups", trek_sport: "Treks & sports",
};
export class ApiError extends Error {
  detail: unknown;
  constructor(message: string, detail: unknown) {super(message); this.detail = detail;}
}
export async function api<T>(path: string, token = "", options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {"Content-Type": "application/json", ...(token ? {Authorization: `Bearer ${token}`} : {}), ...options.headers},
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = result.detail;
    const message = typeof detail === "string" ? detail
      : Array.isArray(detail) ? detail.map((item) => item.msg).join("; ")
      : detail?.message || "Something went wrong. Please try again.";
    throw new ApiError(message, detail);
  }
  return result as T;
}
export const csv = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean);
export const skillsFromText = csv;
export const skillsText = (skills: string[]) => skills.join(", ");
export function scheduleLabel(schedule?: Schedule) {
  if (!schedule || schedule.kind === "undecided") return "Schedule to be decided";
  if (schedule.kind === "single") return schedule.start_date || "Date to be confirmed";
  if (schedule.kind === "range") return `${schedule.start_date} to ${schedule.end_date}`;
  return `Recurring ${(schedule.weekdays || []).map((day) => ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day]).join(", ")} · ${schedule.start_date} to ${schedule.end_date}`;
}
