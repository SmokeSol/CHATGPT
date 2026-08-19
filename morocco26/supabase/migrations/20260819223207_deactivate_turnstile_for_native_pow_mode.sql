update public.asv2_security_config
set turnstile_required=false,
    turnstile_site_key=null,
    updated_at=now()
where config_id='PUBLIC_V1'
  and protection_mode='POW';
