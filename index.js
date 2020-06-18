import React from 'react';
import ReactDOM from 'react-dom';
import './css/index.css';
import App from './App';
import * as serviceWorker from './serviceWorker';
import store from './components/Redux/redux-store';
import {BrowserRouter} from "react-router-dom";
import {Provider} from "react-redux";

	ReactDOM.render(
		<BrowserRouter>
			<Provider store={store}>
				<App />
			</Provider>
		</BrowserRouter>,
		document.getElementById('root'));

serviceWorker.register();