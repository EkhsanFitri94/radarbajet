-- =====================================================================
-- fix_grants.sql — tampal projek yang sudah jalankan schema.sql
-- tetapi dapat 42501 "permission denied for table"
-- =====================================================================
-- Jalankan SEKALI di SQL Editor. Selamat dijalankan berulang.
-- Setiap blok berasingan; kalau satu gagal, yang lain tetap jalan.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. GRANT asas
--    RLS menyaring BARIS. GRANT memberi AKSES JADUAL.
--    Kedua-duanya diperlukan. Tanpa GRANT, PostgREST pulang 42501.
-- ---------------------------------------------------------------------
grant usage on schema public to anon, authenticated;

-- Pelawat (anon): baca sahaja
grant select on public.kedai to anon;
grant select on public.harga to anon;

-- Pengguna berdaftar
grant select on public.kedai  to authenticated;
grant insert, update on public.kedai to authenticated;

grant select on public.harga  to authenticated;
grant insert, delete on public.harga to authenticated;

-- Profil: SELECT penuh, tetapi UPDATE hanya lajur mata & email.
-- Tanpa sekatan lajur, pengguna boleh set peranan='merchant' pada diri
-- sendiri dan kemudian terbit harga bertanda "Peniaga".
grant select on public.profil to authenticated;
grant insert on public.profil to authenticated;
grant update (mata, email) on public.profil to authenticated;

-- Identiti (bigint generated ... identity) perlukan akses sequence
grant usage, select on all sequences in schema public to authenticated;


-- ---------------------------------------------------------------------
-- 2. Semak RLS benar-benar hidup
-- ---------------------------------------------------------------------
alter table public.profil enable row level security;
alter table public.kedai  enable row level security;
alter table public.harga  enable row level security;


-- ---------------------------------------------------------------------
-- 3. Bucket `resit`
--    Kalau blok ini gagal dengan "permission denied for table buckets",
--    cipta bucket melalui Dashboard: Storage -> New bucket
--      name            : resit
--      public          : OFF
--      file size limit : 5 MB
--      allowed MIME    : image/jpeg, image/png, image/webp
-- ---------------------------------------------------------------------
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('resit', 'resit', false, 5242880, array['image/jpeg', 'image/png', 'image/webp'])
on conflict (id) do update
    set public             = excluded.public,
        file_size_limit    = excluded.file_size_limit,
        allowed_mime_types = excluded.allowed_mime_types;


-- ---------------------------------------------------------------------
-- 4. Polisi storage
--    Laluan fail mesti {auth.uid()}/namafail.png
-- ---------------------------------------------------------------------
drop policy if exists resit_muat_naik  on storage.objects;
drop policy if exists resit_baca_sendiri on storage.objects;
drop policy if exists resit_padam_sendiri on storage.objects;

create policy resit_muat_naik on storage.objects for insert
    to authenticated with check (
        bucket_id = 'resit'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy resit_baca_sendiri on storage.objects for select
    to authenticated using (
        bucket_id = 'resit'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

create policy resit_padam_sendiri on storage.objects for delete
    to authenticated using (
        bucket_id = 'resit'
        and (storage.foldername(name))[1] = auth.uid()::text
    );


-- ---------------------------------------------------------------------
-- 5. Pengesahan
-- ---------------------------------------------------------------------
-- Selepas jalankan, ujian ini dari terminal MESTI pulang [] (bukan 42501):
--
--   curl "https://<ref>.supabase.co/rest/v1/kedai?select=id&limit=1" ^
--        -H "apikey: <publishable key>" -H "Authorization: Bearer <publishable key>"
--
-- []   = GRANT betul, RLS hidup, tiada data lagi  -> bagus
-- 42501 = GRANT masih tiada                        -> blok 1 tak jalan
-- data = RLS mati                                  -> bahaya
