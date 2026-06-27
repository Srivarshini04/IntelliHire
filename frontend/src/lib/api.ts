import type {
  Candidate,
  CandidateDetail,
  CandidateListItem,
  Job,
  RankingItem,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function createJob(title: string, description: string): Promise<Job> {
  return request<Job>("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description }),
  });
}

export async function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}`);
}

export async function listJobs(): Promise<Job[]> {
  return request<Job[]>("/jobs");
}

export async function deleteJob(jobId: string): Promise<{ deleted: boolean; candidates_removed: number }> {
  return request(`/jobs/${jobId}`, { method: "DELETE" });
}

export async function listJobCandidates(jobId: string): Promise<CandidateListItem[]> {
  return request<CandidateListItem[]>(`/jobs/${jobId}/candidates`);
}

export async function uploadCandidate(formData: FormData): Promise<Candidate> {
  return request<Candidate>("/candidates", {
    method: "POST",
    body: formData,
  });
}

export async function analyzeCandidate(candidateId: string): Promise<{ status: string }> {
  return request(`/candidates/${candidateId}/analyze`, { method: "POST" });
}

export async function runJobAnalysis(jobId: string): Promise<{ results: unknown[] }> {
  return request(`/analysis/jobs/${jobId}/run`, { method: "POST" });
}

export async function getRankings(jobId: string): Promise<RankingItem[]> {
  return request<RankingItem[]>(`/jobs/${jobId}/rankings`);
}

export async function getCandidateDetail(candidateId: string): Promise<CandidateDetail> {
  return request<CandidateDetail>(`/candidates/${candidateId}`);
}
