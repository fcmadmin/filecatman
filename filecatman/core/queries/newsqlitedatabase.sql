CREATE TABLE IF NOT EXISTS `items` (
    `item_id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    `item_name` TEXT NOT NULL,
    `type_id` TEXT NOT NULL,
    `item_source` TEXT DEFAULT (''),
    `item_time` TEXT DEFAULT ('0000-00-00 00:00:00'),
    `item_description` TEXT DEFAULT ('')
);
CREATE UNIQUE INDEX IF NOT EXISTS `item_name_type` ON `items` (`item_name`,`type_id`);
CREATE INDEX IF NOT EXISTS `type_id` ON `items` (`type_id`);

CREATE TABLE IF NOT EXISTS `terms` (
	`term_id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	`term_name` TEXT NOT NULL,
	`term_slug` TEXT NOT NULL,
	`term_taxonomy` TEXT NOT NULL,
	`term_description` TEXT NULL,
	`term_parent` INTEGER NULL default NULL,
	`term_count` INTEGER NOT NULL default 0,
	FOREIGN KEY (`term_parent`) REFERENCES terms(`term_id`) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS `term_slug_taxonomy` ON `terms` (`term_slug`, `term_taxonomy`);
CREATE INDEX IF NOT EXISTS `term_taxonomy` ON `terms` (`term_taxonomy`);

CREATE TABLE IF NOT EXISTS `term_relationships` (
	`item_id` INTEGER NOT NULL,
	`term_id` INTEGER NOT NULL,
	PRIMARY KEY (`item_id`,`term_id`),
	FOREIGN KEY (`item_id`) REFERENCES items(`item_id`) ON DELETE CASCADE,
	FOREIGN KEY (`term_id`) REFERENCES terms(`term_id`) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `term_id` ON `term_relationships` (`term_id`);

CREATE TABLE IF NOT EXISTS `options` (
	`option_id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	`option_name` TEXT NOT NULL,
	`option_value` TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS `option_name` ON `options` (`option_name`);

CREATE TABLE IF NOT EXISTS `item_types` (
	`type_id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	`noun_name` TEXT NOT NULL,
	`plural_name` TEXT NOT NULL,
	`dir_name` TEXT NOT NULL,
	`table_name` TEXT NOT NULL,
	`icon_name` TEXT NOT NULL,
	`enabled` INTEGER NOT NULL default 1,
	`extensions` TEXT NOT NULL default ''
);
CREATE UNIQUE INDEX IF NOT EXISTS `item_types_table_plural` ON `item_types` (`table_name`, `plural_name`);

CREATE TABLE IF NOT EXISTS `taxonomies` (
	`taxonomy_id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	`noun_name` TEXT NOT NULL,
	`plural_name` TEXT NOT NULL,
	`dir_name` TEXT NOT NULL,
	`table_name` TEXT NOT NULL,
	`icon_name` TEXT NOT NULL,
	`enabled` INTEGER NOT NULL default 1,
	`has_children` INTEGER NOT NULL default 1,
	`is_tags` INTEGER NOT NULL default 0
);
CREATE UNIQUE INDEX IF NOT EXISTS `taxonomies_table_plural` ON `taxonomies` (`table_name`, `plural_name`);

PRAGMA foreign_keys = 1;
