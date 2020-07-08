import React, {useState, useEffect} from 'react';
import {connect} from "react-redux";
import * as axios from "axios";
import Header from "./Header";
import {authUser} from "../Redux/authReducer";

const HeaderContainer = (props) => {
	
	let [preloaderOn, setPreloaderOn] = useState(false);
	
	// хук для запроса на серв. списка пользователей. Производится запись пришедшего списка через CB
	useEffect(() => {
		setPreloaderOn(true);
		// запрос с параметром на кроссдоменную аутентификацию {withCredentials:true}
		axios.get(`https://social-network.samuraijs.com/api/1.0/auth/me`, {withCredentials:true}).then(response => {
			if (response.data.resultCode === 0) {
				props.authUser(response.data.data)
			}
			setPreloaderOn(false);
		})
	}, []);
	
	return <Header
		authData={props.authData}
	/>;
};

const mapStateToProps = (state) => {
	return ({
		authData: state.auth,
	})
};

export default connect(mapStateToProps, {
	// callBacks for mapDispatchToProps
	authUser,
})(HeaderContainer);



