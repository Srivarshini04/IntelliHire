export interface RoleBlueprint {
  role: string;
  skills: string[];
  behavioral_traits: string[];
  weights: Record<string, number>;
  required_evidence: string[];
}

export interface Job {
  job_id: string;
  title: string;
  description: string;
  role_blueprint?: RoleBlueprint;
  created_at?: string;
  candidate_count?: number;
}

export interface Candidate {
  candidate_id: string;
  job_id: string;
  name: string;
  email?: string;
  github_url?: string;
  linkedin_url?: string;
}

export interface CandidateListItem {
  candidate_id: string;
  name: string;
  email?: string;
  github_url?: string;
  linkedin_url?: string;
  has_resume: boolean;
  analyzed: boolean;
  created_at?: string;
}

export interface RankingItem {
  candidate_id: string;
  candidate: string;
  fit_score: number;
  risk: number;
  hti: number;
  confidence: number;
  rank: number;
  recommendation?: string;
}

export interface CapabilityProfile {
  technical: number;
  execution: number;
  ownership: number;
  learning_velocity: number;
  problem_solving: number;
  domain_expertise: number;
  capability_score: number;
}

export interface RiskProfile {
  evidence_risk: number;
  role_gap_risk: number;
  credibility_risk: number;
  risk_score: number;
}

export interface HTIProfile {
  visibility_score: number;
  hti_score: number;
}

export interface Explanation {
  strengths: string[];
  risks: string[];
  reason: string;
}

export interface CandidateDetail {
  candidate_id: string;
  name: string;
  capability?: CapabilityProfile;
  risk?: RiskProfile;
  hti?: HTIProfile;
  evidence: Array<{
    source_type: string;
    source_url?: string;
    relevance_score?: number;
  }>;
  explanation?: Explanation;
}
