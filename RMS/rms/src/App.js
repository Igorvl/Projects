import React from 'react';
import s from './css/App.module.css';
import {Layout} from 'antd';
import Advantage from "./Components/Advantage/Advantage";
import Strategy from "./Components/Strategy/Strategy";
import Feedback from "./Components/Feedback/Feedback";

// AntD
const {Header, Footer, Content} = Layout;

function App() {
	
	return (
		<div className={s.App} >
			<Header>
				{/*Header*/}
			</Header>
			<Content  className={s.App_content}>
				<Advantage/>
				<Strategy/>
				<Feedback/>
			</Content>
			<Footer>
				{/*Footer*/}
			</Footer>
		</div>
	);
}

export default App;
