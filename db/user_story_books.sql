
-- ----------------------------
-- Table structure for user_story_books
-- ----------------------------
DROP TABLE IF EXISTS `user_story_books`;
CREATE TABLE `user_story_books` (
  `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL COMMENT '用户ID',
  `role_id` bigint(20) NOT NULL COMMENT '角色ID',
  `story_id` bigint(20) NOT NULL COMMENT '故事ID',
  `story_book_path` varchar(255) NOT NULL COMMENT '有声故事书路径',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_user_role` (`user_id`, `role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户有声故事书表';

