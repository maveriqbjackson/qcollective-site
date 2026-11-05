-- Q HQ and Q Console: real email sign-in (run once in Supabase > SQL Editor).
-- Admin list. RLS on with no policies, so nobody can read or change it from the site.
create table if not exists public.hq_admins (
  email text primary key,
  added_at timestamptz not null default now()
);
alter table public.hq_admins enable row level security;
insert into public.hq_admins (email) values
  ('team@theqcollective.org'),
  ('maveriqbjackson@proton.me')
on conflict do nothing;

-- True only for a signed-in user whose verified email is on the list.
create or replace function public.is_hq_admin()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.hq_admins a
                 where lower(a.email) = lower(coalesce(auth.jwt() ->> 'email', '')));
$$;
revoke all on function public.is_hq_admin() from public, anon;
grant execute on function public.is_hq_admin() to authenticated;

-- Private HQ notes and to-dos: admins only.
create table if not exists public.hq_private (
  key text primary key,
  body jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.hq_private enable row level security;
drop policy if exists hq_private_admin_all on public.hq_private;
create policy hq_private_admin_all on public.hq_private for all to authenticated
  using (public.is_hq_admin()) with check (public.is_hq_admin());
