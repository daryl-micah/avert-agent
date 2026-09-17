-- GitHub App installation that indexed this repository. Lets the dashboard
-- scope an inventory to the connected installation. NULL for repositories
-- indexed from a local path.
ALTER TABLE repository ADD COLUMN github_installation_id BIGINT;
CREATE INDEX repository_github_installation_id_idx ON repository (github_installation_id);
