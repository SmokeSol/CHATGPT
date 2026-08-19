create table if not exists public.asv2_social_previews (
  assignment_id uuid primary key references public.asv2_assignments(assignment_id) on delete cascade,
  cohort_id text not null,
  work_id text not null,
  provider text,
  model_label text,
  r0_sha256 text not null,
  engine_version text not null,
  config_version text not null,
  config_status text not null,
  graph_sha256 text not null,
  profiles jsonb not null,
  graph jsonb not null,
  summary jsonb not null,
  created_at timestamptz not null default now(),
  unique (cohort_id, work_id)
);

create index if not exists asv2_social_previews_created_at_idx on public.asv2_social_previews(created_at desc);
create index if not exists asv2_social_previews_provider_idx on public.asv2_social_previews(provider);

alter table public.asv2_social_previews enable row level security;
revoke all on table public.asv2_social_previews from anon, authenticated;

create or replace function public.asv2_public_social_status()
returns table(
  state text,
  target_work_items integer,
  completed bigint,
  socialized bigint,
  pending_social bigint,
  family_edges bigint,
  work_edges bigint,
  neighborhood_edges bigint,
  mean_r1_party_shift_l1 double precision,
  mean_r2_party_shift_l1 double precision,
  mean_r1_turnout_abs_shift double precision,
  mean_r2_turnout_abs_shift double precision,
  config_status text
)
language sql
security definer
set search_path to 'public'
as $function$
  with c as (
    select state, target_work_items
    from public.asv2_cohorts
    where cohort_id='AS2_PUBLIC_V1'
  ), a as (
    select count(*)::bigint as completed
    from public.asv2_assignments
    where cohort_id='AS2_PUBLIC_V1' and status='COMPLETED'
  ), s as (
    select
      count(*)::bigint as socialized,
      coalesce(sum((summary->'edges'->>'family')::bigint),0)::bigint as family_edges,
      coalesce(sum((summary->'edges'->>'work')::bigint),0)::bigint as work_edges,
      coalesce(sum((summary->'edges'->>'neighborhood')::bigint),0)::bigint as neighborhood_edges,
      coalesce(avg((summary->>'mean_r1_party_shift_l1')::double precision),0)::double precision as mean_r1_party_shift_l1,
      coalesce(avg((summary->>'mean_r2_from_r0_party_shift_l1')::double precision),0)::double precision as mean_r2_party_shift_l1,
      coalesce(avg((summary->>'mean_r1_turnout_abs_shift')::double precision),0)::double precision as mean_r1_turnout_abs_shift,
      coalesce(avg((summary->>'mean_r2_from_r0_turnout_abs_shift')::double precision),0)::double precision as mean_r2_turnout_abs_shift,
      coalesce(max(config_status),'ILLUSTRATIVE_NOT_CALIBRATED') as config_status
    from public.asv2_social_previews
    where cohort_id='AS2_PUBLIC_V1'
  )
  select c.state, c.target_work_items, a.completed, s.socialized,
         greatest(a.completed-s.socialized,0)::bigint as pending_social,
         s.family_edges,s.work_edges,s.neighborhood_edges,
         s.mean_r1_party_shift_l1,s.mean_r2_party_shift_l1,
         s.mean_r1_turnout_abs_shift,s.mean_r2_turnout_abs_shift,s.config_status
  from c cross join a cross join s;
$function$;

revoke all on function public.asv2_public_social_status() from public, anon, authenticated;
grant execute on function public.asv2_public_social_status() to service_role;
