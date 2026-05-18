create table if not exists devices (
  id text primary key,
  token_hash text not null,
  created_at text not null,
  updated_at text not null,
  last_seen_at text not null
);

create table if not exists saved_items (
  device_id text not null,
  item_key text not null,
  updated_at text not null,
  primary key (device_id, item_key),
  foreign key (device_id) references devices(id) on delete cascade
);

create index if not exists idx_saved_items_item_key on saved_items(item_key);

create table if not exists web_push_subscriptions (
  device_id text not null,
  endpoint text primary key,
  p256dh text not null,
  auth text not null,
  user_agent text not null default '',
  enabled integer not null default 1,
  updated_at text not null,
  foreign key (device_id) references devices(id) on delete cascade
);

create index if not exists idx_web_push_device on web_push_subscriptions(device_id);

create table if not exists telegram_links (
  device_id text primary key,
  chat_id text not null,
  username text not null default '',
  enabled integer not null default 1,
  updated_at text not null,
  foreign key (device_id) references devices(id) on delete cascade
);

create index if not exists idx_telegram_chat on telegram_links(chat_id);

create table if not exists telegram_pairing_tokens (
  token_hash text primary key,
  device_id text not null,
  expires_at text not null,
  used_at text,
  foreign key (device_id) references devices(id) on delete cascade
);

create table if not exists notification_log (
  id integer primary key autoincrement,
  stock_updated_at text not null,
  item_key text not null,
  channel text not null,
  target_hash text not null,
  sent_at text not null,
  status text not null,
  error text not null default '',
  unique (stock_updated_at, item_key, channel, target_hash)
);

create table if not exists rate_limits (
  key text not null,
  window_start text not null,
  request_count integer not null,
  primary key (key, window_start)
);
