-- Supabase → SQL Editor → New query → Run

create table if not exists products (
  id bigint primary key,
  emoji text default '🎮',
  grp text not null default 'cheap',
  price bigint not null default 0,
  level int not null default 0,
  skins int not null default 0,
  sold boolean not null default false,
  img text default '',
  name_uz text not null,
  name_ru text not null,
  desc_uz text default '',
  desc_ru text default '',
  updated_at timestamptz default now()
);

create table if not exists orders (
  id bigint generated always as identity primary key,
  customer_name text,
  username text,
  telegram_id text,
  items jsonb,
  total bigint,
  created_at timestamptz default now()
);

-- RLS yoqilgan, policy YO'Q: brauzerdan (anon kalit bilan) hech kim o'qiy/yoza olmaydi.
-- Faqat sizning Flask serveringiz (service_role kaliti) ishlaydi.
alter table products enable row level security;
alter table orders enable row level security;
