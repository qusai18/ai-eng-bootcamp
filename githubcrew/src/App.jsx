import { Console, Crew, Footer, Header, Hero, Overview, Report } from './components.jsx';
import { useMission } from './useMission.js';

export default function App() {
  const mission = useMission();
  return (
    <>
      <Header onDeploy={mission.focusBrief} />
      <Hero mission={mission} />
      <Overview />
      <Crew />
      <Console mission={mission} />
      <Report mission={mission} />
      <Footer />
    </>
  );
}
