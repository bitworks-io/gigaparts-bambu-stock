create table if not exists telegram_saved_items (
  chat_id text not null,
  item_key text not null,
  updated_at text not null,
  primary key (chat_id, item_key)
);

create index if not exists idx_telegram_saved_items_item_key on telegram_saved_items(item_key);

insert or ignore into telegram_saved_items (chat_id, item_key, updated_at)
select tl.chat_id, si.item_key, datetime('now')
from telegram_links tl
join saved_items si on si.device_id = tl.device_id
where tl.enabled = 1;
