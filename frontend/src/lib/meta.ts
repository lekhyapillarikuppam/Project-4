import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function useMeta() {
  return useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
}

export function useCities() {
  return useQuery({ queryKey: ["cities"], queryFn: api.cities, staleTime: Infinity });
}

export function useCityName() {
  const { data } = useCities();
  return (code: string) => data?.find((c) => c.code === code)?.name ?? code;
}
