import React from 'react';
import s from './css/App.module.css';
// import FeedBack from "./Components/feedback";
import {Layout} from 'antd';
import Advantage from "./Components/Advantage";

const {Header, Footer, Content} = Layout;

function App() {
	return (
		<div className={s.App}>
			<Header>
				{/*Header*/}
			</Header>
			<Content  className={s.App_content}>
				<Advantage/>
				{/*<FeedBack/>*/}
			</Content>
			<Footer>
				{/*Footer*/}
			</Footer>
		</div>
	);
}

export default App;
