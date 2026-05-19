-- Create extensions if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant permissions
GRANT CONNECT ON DATABASE referral_bot TO referral_user;
GRANT USAGE ON SCHEMA public TO referral_user;
GRANT CREATE ON SCHEMA public TO referral_user;
