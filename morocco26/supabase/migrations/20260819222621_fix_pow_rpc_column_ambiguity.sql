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

  update public.asv2_pow_challenges ch set status='EXPIRED'
   where ch.status='ACTIVE' and ch.expires_at < now();

  select count(*) into v_recent_ip
  from public.asv2_pow_challenges ch
  where ch.ip_hash=p_ip_hash and ch.issued_at >= now()-interval '1 hour';
  if v_recent_ip >= v_cfg.max_pow_challenges_per_ip_hour then raise exception 'RATE_LIMIT_POW_IP_HOUR'; end if;

  select count(*) into v_recent_browser
  from public.asv2_pow_challenges ch
  where ch.browser_hash=p_browser_hash and ch.issued_at >= now()-interval '1 hour';
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
  update public.asv2_pow_challenges ch
     set status='CONSUMED', consumed_at=now()
   where ch.challenge_id=p_challenge_id
     and ch.browser_hash=p_browser_hash
     and ch.ip_hash=p_ip_hash
     and ch.status='ACTIVE'
     and ch.expires_at>=now()
  returning ch.challenge_id into v_id;

  if v_id is null then
    update public.asv2_pow_challenges ch set status='EXPIRED'
     where ch.challenge_id=p_challenge_id and ch.status='ACTIVE' and ch.expires_at<now();
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
