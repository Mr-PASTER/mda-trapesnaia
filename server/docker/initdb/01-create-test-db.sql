-- Дополнительные БД создаются при первом старте контейнера.
-- mda и mda_test — основные; остальные — для параллельных прогонов тестов.
CREATE DATABASE mda_test OWNER mda;
CREATE DATABASE mda_test_b1 OWNER mda;
CREATE DATABASE mda_test_b2 OWNER mda;
CREATE DATABASE mda_test_b3 OWNER mda;
