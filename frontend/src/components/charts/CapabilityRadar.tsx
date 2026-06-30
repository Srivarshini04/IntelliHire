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
          <PolarGrid stroke="rgba(255,255,255,0.12)" />
          <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fill: "rgba(233,233,242,0.55)" }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
          <Radar name="Capability" dataKey="value" stroke="#a855f7" fill="#a855f7" fillOpacity={0.35} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
