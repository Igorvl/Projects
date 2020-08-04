import React, {useState, useEffect} from 'react';
import {connect} from "react-redux";
import Header from "./Header";
import {authTh} from "../Redux/authReducer";
import {profileRequest} from "../Redux/usersReducer";

const HeaderContainer = (props) => {
	
	let [, setPreloaderOn] = useState(false);
	let {authTh, id} = props;
	// хук для запроса на серв. списка пользователей. Производится запись пришедшего списка через CB
	useEffect(() => {
		setPreloaderOn(true);
		// запрос с параметром на кроссдоменную аутентификацию {withCredentials:true}
		authTh();
		profileRequest(id);
		setPreloaderOn(false);
	}, [authTh, id]);
	
	return <Header {...props.authData} profileRequest={props.profileRequest}/>;
};

const mapStateToProps = (state) => {
	return ({
		authData: state.auth,
	})
};

export default connect(mapStateToProps, {authTh, profileRequest})(HeaderContainer);



