CREATE PROCEDURE duplicate_configuration_group (IN configuration_group_name VARCHAR(45), IN new_group_name VARCHAR(45))
BEGIN
	DECLARE no_more_names INTEGER DEFAULT 0;
    DECLARE _c_configuration_name VARCHAR(45);

    DECLARE name_cursor CURSOR FOR SELECT name FROM configuration_names;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET no_more_names = 1;
    
    DROP TEMPORARY TABLE IF EXISTS `group_copy`;
    DROP TEMPORARY TABLE IF EXISTS `configuration_names`;
    DROP TEMPORARY TABLE IF EXISTS `configurations_copy`;

    -- Copy the group row to temporary table and insert the copied values with new id
	CREATE TEMPORARY TABLE group_copy SELECT * FROM test_configuration_group where name = configuration_group_name;
	-- Drop id-column to make inserting easier
	ALTER TABLE group_copy DROP COLUMN id;
	UPDATE group_copy SET name = new_group_name;
	-- 0 passed as id makes the server autoincrement the next sequence value as new id, otherwise insert all copied data
	INSERT INTO test_configuration_group SELECT 0, group_copy.* FROM group_copy;

    -- Store names of configurations to be copied to iterate through later
	CREATE TEMPORARY TABLE configuration_names SELECT name FROM test_configuration WHERE configuration_group = (SELECT id FROM test_configuration_group WHERE name = configuration_group_name);

    -- Copy the actual configuration rows in similar manner to the configuration group process
	CREATE TEMPORARY TABLE configurations_copy SELECT * FROM test_configuration WHERE configuration_group = (SELECT id FROM test_configuration_group WHERE name = configuration_group_name);
	ALTER TABLE configurations_copy DROP COLUMN id;
	-- Update the configuration_group to point to the newly generated group
	UPDATE configurations_copy SET configuration_group = (SELECT id FROM test_configuration_group WHERE name = new_group_name);
	INSERT INTO test_configuration SELECT 0, configurations_copy.* FROM configurations_copy;
    
    OPEN name_cursor;
    create_parameters: LOOP
		FETCH name_cursor INTO _c_configuration_name;
		
		IF no_more_names = 1 THEN
		LEAVE create_parameters;
		END IF;	
        -- Copy the individual test parameter table values for each configurable test in the same way as  was previously
        -- done with configurations and group, insert new values with new configuration ids

        -- Drop the temporary table created in the previous loop round so we can create a new one for this round
        DROP TEMPORARY TABLE IF EXISTS `linearity_copy`;
        -- Copy the parameters that were linked to the old configuration
        CREATE TEMPORARY TABLE linearity_copy SELECT * FROM linearity_parameters WHERE test_configuration =
			(
				SELECT test_configuration.id 
				FROM test_configuration 
                JOIN test_configuration_group ON test_configuration.configuration_group = test_configuration_group.id
				WHERE test_configuration.name = _c_configuration_name AND test_configuration_group.name = configuration_group_name
			);
        
        ALTER TABLE linearity_copy DROP COLUMN id;

        -- Update the test_configuration-column to point to the new configuration
        UPDATE linearity_copy SET test_configuration = 
			(
			SELECT test_configuration.id 
			FROM test_configuration 
			JOIN test_configuration_group ON test_configuration.configuration_group = test_configuration_group.id 
			WHERE test_configuration.name = _c_configuration_name AND test_configuration_group.name = new_group_name
			);
		INSERT INTO linearity_parameters SELECT 0, linearity_copy.* FROM linearity_copy;

        -- The process is exactly the same for all the parameter tables from here on, just the names change
        DROP TEMPORARY TABLE IF EXISTS `grid_accuracy_copy`;
        CREATE TEMPORARY TABLE grid_accuracy_copy SELECT * FROM grid_accuracy_parameters WHERE test_configuration = 
			(
				SELECT test_configuration.id 
				FROM test_configuration 
                JOIN test_configuration_group ON test_configuration.configuration_group = test_configuration_group.id
				WHERE test_configuration.name = _c_configuration_name AND test_configuration_group.name = configuration_group_name
			);
        
        ALTER TABLE grid_accuracy_copy DROP COLUMN id;
        
        UPDATE grid_accuracy_copy SET test_configuration = 
			(
			SELECT test_configuration.id 
			FROM test_configuration 
			JOIN test_configuration_group ON test_configuration.configuration_group = test_configuration_group.id 
			WHERE test_configuration.name = _c_configuration_name AND test_configuration_group.name = new_group_name
			);
		INSERT INTO grid_accuracy_parameters SELECT 0, grid_accuracy_copy.* FROM grid_accuracy_copy;
        
        DROP TEMPORARY TABLE IF EXISTS `tapping_repeatability_copy`;
        CREATE TEMPORARY TABLE tapping_repeatability_copy SELECT * FROM tapping_repeatability_parameters WHERE test_configuration = 
			(
				SELECT test_configuration.id 
				FROM test_configuration 
                JOIN test_configuration_group ON test_configuration.configuration_group = test_configuration_group.id
				WHERE test_configuration.name = _c_configuration_name AND test_configuration_group.name = configuration_group_name
			);
        
        ALTER TABLE tapping_repeatability_copy DROP COLUMN id;
        
        UPDATE tapping_repeatability_copy SET test_configuration = 
			(
			SELECT test_configuration.id 
			FROM test_configuration 
			JOIN test_configuration_group ON test_configuration.configuration_group = test_configuration_group.id 
			WHERE test_configuration.name = _c_configuration_name AND test_configuration_group.name = new_group_name
			);
		INSERT INTO tapping_repeatability_parameters SELECT 0, tapping_repeatability_copy.* FROM tapping_repeatability_copy;
        
        DROP TEMPORARY TABLE IF EXISTS `stationary_jitter_copy`;
        CREATE TEMPORARY TABLE stationary_jitter_copy SELECT * FROM stationary_jitter_static_noise_parameters WHERE test_configuration = 
			(
				SELECT test_configuration.id 
				FROM test_configuration 
                JOIN test_configuration_group ON test_configuration.configuration_group = test_configuration_group.id
				WHERE test_configuration.name = _c_configuration_name AND test_configuration_group.name = configuration_group_name
			);
        
        ALTER TABLE stationary_jitter_copy DROP COLUMN id;
        
        UPDATE stationary_jitter_copy SET test_configuration = 
			(
			SELECT test_configuration.id 
			FROM test_configuration 
			JOIN test_configuration_group ON test_configuration.configuration_group = test_configuration_group.id 
			WHERE test_configuration.name = _c_configuration_name AND test_configuration_group.name = new_group_name
			);
		INSERT INTO stationary_jitter_static_noise_parameters SELECT 0, stationary_jitter_copy.* FROM stationary_jitter_copy;
    END LOOP create_parameters;
    CLOSE name_cursor;
END