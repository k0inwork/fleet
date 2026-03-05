import { JulesClient } from './src/lib/jules/client.js';

async function battleTest() {
  const apiKey = process.env.JULES_API_KEY;
  if (!apiKey) {
    console.error('❌ JULES_API_KEY environment variable is not set. Cannot run battle test.');
    process.exit(1);
  }

  console.log('🚀 Initializing JulesClient with API Key...');
  // Max retries is 2 by default
  const client = new JulesClient(apiKey);

  try {
    console.log('\\n📡 Testing: listSources()');
    const sourcesResponse = await client.listSources(5);
    console.log('✅ Success! Found sources:', sourcesResponse.sources?.length || 0);

    if (sourcesResponse.sources && sourcesResponse.sources.length > 0) {
      console.log('   First source:', sourcesResponse.sources[0].name);

      console.log('\\n📡 Testing: getSource()');
      const sourceDetail = await client.getSource(sourcesResponse.sources[0].name);
      console.log('✅ Success! Source URL:', sourceDetail.url);
    } else {
      console.log('⚠️ No sources found to test getSource() against.');
    }

    console.log('\\n📡 Testing: listSessions()');
    const sessionsResponse = await client.listSessions(5);
    console.log('✅ Success! Found sessions:', sessionsResponse.sessions?.length || 0);

    if (sessionsResponse.sessions && sessionsResponse.sessions.length > 0) {
      const activeSession = sessionsResponse.sessions[0];
      console.log('   First session:', activeSession.name, '| State:', activeSession.state);

      console.log('\\n📡 Testing: getSession()');
      const sessionDetail = await client.getSession(activeSession.name);
      console.log('✅ Success! Session state verified:', sessionDetail.state);

      console.log('\\n📡 Testing: listActivities()');
      const activitiesResponse = await client.listActivities(activeSession.name, 5);
      console.log('✅ Success! Found activities:', activitiesResponse.activities?.length || 0);
    } else {
      console.log('⚠️ No sessions found to test getSession() or listActivities() against.');
    }

    console.log('\\n🎉 All battle tests completed successfully!');
  } catch (error) {
    console.error('\\n❌ Battle test failed with error:');
    if (error.response) {
       console.error(`Status: ${error.statusCode}`);
       console.error(`Response Body: ${error.response}`);
    } else {
       console.error(error);
    }
  }
}

battleTest();
