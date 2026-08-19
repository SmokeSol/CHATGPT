alter table public.asv2_security_config add column if not exists protection_mode text not null default 'POW';
alter table public.asv2_security_config add column if not exists pow_difficulty_bits integer not null default 16;
alter table public.asv2_security_config add column if not exists pow_challenge_ttl_seconds integer not null default 300;
alter table public.asv2_security_config add column if not exists max_pow_challenges_per_ip_hour integer not null default 30;
alter table public.asv2_security_config add column if not exists max_pow_challenges_per_browser_hour integer not null default 8;

update public.asv2_security_config
set protection_mode='POW',
    pow_difficulty_bits=16,
    pow_challenge_ttl_seconds=300,
    max_pow_challenges_per_ip_hour=30,
    max_pow_challenges_per_browser_hour=8,
    updated_at=now()
where config_id='PUBLIC_V1';

create table if not exists public.asv2_pow_challenges (
  challenge_id uuid primary key default gen_random_uuid(),
  browser_hash text not null,
  ip_hash text not null,
  nonce text not null unique,
  difficulty_bits integer not null,
  status text not null default 'ACTIVE' check (status in ('ACTIVE','CONSUMED','EXPIRED')),
  issued_at timestamptz not null default now(),
  expires_at timestamptz not null,
  consumed_at timestamptz
);
create index if not exists asv2_pow_challenges_ip_issued_idx on public.asv2_pow_challenges(ip_hash, issued_at desc);
create index if not exists asv2_pow_challenges_browser_issued_idx on public.asv2_pow_challenges(browser_hash, issued_at desc);
alter table public.asv2_pow_challenges enable row level security;
revoke all on public.asv2_pow_challenges from anon, authenticated, public;
grant all on public.asv2_pow_challenges to service_role;

create or replace function public.asv2_issue_pow_challenge(
  p_browser_hash text,
  p_ip_hash text,
  p_nonce text
) returns table(challenge_id uuid, difficulty_bits integer, expires_at timestamptz)
language plpgsql
security definer
set search_path to 'public','pg_temp'
as $$
declare
  v_cfg public.asv2_security_config%rowtype;
  v_recent_ip bigint;
  v_recent_browser bigint;
  v_ch public.asv2_pow_challenges%rowtype;
begin
  if coalesce(length(p_browser_hash),0) < 32 or coalesce(length(p_ip_hash),0) < 32 or coalesce(length(p_nonce),0) < 20 then
    raise exception 'POW_ID_INVALID';
  end if;
  select * into v_cfg from public.asv2_security_config where config_id='PUBLIC_V1';
  if v_cfg.config_id is null then raise exception 'SECURITY_CONFIG_MISSING'; end if;
  if coalesce(v_cfg.protection_mode,'POW') <> 'POW' then raise exception 'POW_GATE_DISABLED'; end if;

  update public.asv2_pow_challenges set status='EXPIRED'
   where status='ACTIVE' and expires_at < now();

  select count(*) into v_recent_ip
  from public.asv2_pow_challenges
  where ip_hash=p_ip_hash and issued_at >= now()-interval '1 hour';
  if v_recent_ip >= v_cfg.max_pow_challenges_per_ip_hour then raise exception 'RATE_LIMIT_POW_IP_HOUR'; end if;

  select count(*) into v_recent_browser
  from public.asv2_pow_challenges
  where browser_hash=p_browser_hash and issued_at >= now()-interval '1 hour';
  if v_recent_browser >= v_cfg.max_pow_challenges_per_browser_hour then raise exception 'RATE_LIMIT_POW_BROWSER_HOUR'; end if;

  insert into public.asv2_pow_challenges(browser_hash,ip_hash,nonce,difficulty_bits,expires_at)
  values(p_browser_hash,p_ip_hash,p_nonce,v_cfg.pow_difficulty_bits,now()+make_interval(secs=>v_cfg.pow_challenge_ttl_seconds))
  returning * into v_ch;

  insert into public.asv2_security_events(ip_hash,browser_hash,event_type,detail)
  values(p_ip_hash,p_browser_hash,'POW_CHALLENGE_ISSUED',jsonb_build_object('challenge_id',v_ch.challenge_id,'difficulty_bits',v_ch.difficulty_bits));

  challenge_id:=v_ch.challenge_id;
  difficulty_bits:=v_ch.difficulty_bits;
  expires_at:=v_ch.expires_at;
  return next;
end;
$$;

create or replace function public.asv2_consume_pow_challenge(
  p_challenge_id uuid,
  p_browser_hash text,
  p_ip_hash text
) returns table(challenge_id uuid)
language plpgsql
security definer
set search_path to 'public','pg_temp'
as $$
declare
  v_id uuid;
begin
  update public.asv2_pow_challenges
     set status='CONSUMED', consumed_at=now()
   where challenge_id=p_challenge_id
     and browser_hash=p_browser_hash
     and ip_hash=p_ip_hash
     and status='ACTIVE'
     and expires_at>=now()
  returning asv2_pow_challenges.challenge_id into v_id;

  if v_id is null then
    update public.asv2_pow_challenges set status='EXPIRED'
     where challenge_id=p_challenge_id and status='ACTIVE' and expires_at<now();
    raise exception 'POW_CHALLENGE_INVALID_OR_USED';
  end if;

  insert into public.asv2_security_events(ip_hash,browser_hash,event_type,detail)
  values(p_ip_hash,p_browser_hash,'POW_VERIFIED',jsonb_build_object('challenge_id',v_id));

  challenge_id:=v_id;
  return next;
end;
$$;

revoke execute on function public.asv2_issue_pow_challenge(text,text,text) from public, anon, authenticated;
revoke execute on function public.asv2_consume_pow_challenge(uuid,text,text) from public, anon, authenticated;
grant execute on function public.asv2_issue_pow_challenge(text,text,text) to service_role;
grant execute on function public.asv2_consume_pow_challenge(uuid,text,text) to service_role;
