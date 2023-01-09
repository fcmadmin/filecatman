CREATE TABLE IF NOT EXISTS `items`
(
	`item_id` bigint(20) unsigned NOT NULL auto_increment,
	`item_name` varchar(255) NOT NULL,
	`type_id` char(32) NOT NULL,
	`item_source` varchar(255) default '',
	`item_time` datetime default '0000-00-00 00:00:00',
	`item_description` varchar(2000) default '',
	PRIMARY KEY (`item_id`),
	UNIQUE INDEX `item_name_type` (`item_name`,`type_id`),
	INDEX `type_id` (`type_id`)
) DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `terms`
(
	`term_id` bigint(20) unsigned NOT NULL auto_increment,
	`term_name` varchar(255) NOT NULL default '',
	`term_slug` varchar(255) NOT NULL default '',
	`term_taxonomy` varchar(32) NOT NULL default '',
	`term_description` longtext NOT NULL,
	`term_parent` bigint(20) unsigned NULL default NULL,
	`term_count` bigint(20) unsigned NOT NULL default 0,
	PRIMARY KEY  (`term_id`),
	FOREIGN KEY (`term_parent`) REFERENCES terms(`term_id`) ON DELETE SET NULL,
	UNIQUE INDEX `term_slug_taxonomy` (`term_slug`,`term_taxonomy`),
	INDEX `term_taxonomy` (`term_taxonomy`)
) DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `term_relationships` (
	`item_id` bigint(20) unsigned NOT NULL default 0,
	`term_id` bigint(20) unsigned NOT NULL default 0,
	PRIMARY KEY (`item_id`,`term_id`),
	FOREIGN KEY (`item_id`) REFERENCES items(`item_id`) ON DELETE CASCADE,
	FOREIGN KEY (`term_id`) REFERENCES terms(`term_id`) ON DELETE CASCADE,
	INDEX `term_id` (`term_id`)
) DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `options` (
	`option_id` bigint(20) unsigned NOT NULL auto_increment,
	`option_name` varchar(64) NOT NULL,
	`option_value` longtext NOT NULL,
	PRIMARY KEY  (`option_id`),
	UNIQUE INDEX `option_name` (`option_name`)
) DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `item_types` (
	`type_id` bigint(20) unsigned NOT NULL auto_increment,
	`noun_name` varchar(64) NOT NULL,
	`plural_name` varchar(64) NOT NULL,
	`dir_name` varchar(64) NOT NULL,
	`table_name` varchar(64) NOT NULL,
	`icon_name` varchar(64) NOT NULL,
	`enabled` tinyint(1) NOT NULL default 1,
	`extensions` varchar(200) NOT NULL default '',
	PRIMARY KEY  (`type_id`),
	UNIQUE INDEX `item_types_table_plural` (`table_name`,`plural_name`)
) DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `taxonomies` (
	`taxonomy_id` bigint(20) unsigned NOT NULL auto_increment,
	`noun_name` varchar(64) NOT NULL,
	`plural_name` varchar(64) NOT NULL,
	`dir_name` varchar(64) NOT NULL,
	`table_name` varchar(64) NOT NULL,
	`icon_name` varchar(64) NOT NULL,
	`enabled` tinyint(1) NOT NULL default 1,
	`has_children` tinyint(1) NOT NULL default 1,
	`is_tags` tinyint(1) NOT NULL default 0,
	PRIMARY KEY  (`taxonomy_id`),
	UNIQUE INDEX `taxonomies_table_plural` (`table_name`,`plural_name`)
) DEFAULT CHARSET=utf8;
