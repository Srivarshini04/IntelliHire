"use client";

import type { CapabilityProfile } from "@/lib/types";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

interface CapabilityRadarProps {
  capability: CapabilityProfile;
}

export function CapabilityRadar({ capability }: CapabilityRadarProps) {
  const data = [
    { dimension: "Technical", value: capability.technical },
    { dimension: "Execution", value: capability.execution },
    { dimension: "Ownership", value: capability.ownership },
    { dimension: "Learning", value: capability.learning_velocity },
    { dimension: "Problem Solving", value: capability.problem_solving },
    { dimension: "Domain", value: capability.domain_expertise },
  ];

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11 }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} />
          <Radar
            name="Capability"
            dataKey="value"
            stroke="#7c3aed"
            fill="#7c3aed"
            fillOpacity={0.4}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
