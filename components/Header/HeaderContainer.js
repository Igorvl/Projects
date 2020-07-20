import React, {useState, useEffect} from 'react';
import {connect} from "react-redux";
import Header from "./Header";
import {authTh} from "../Redux/authReducer";

const HeaderContainer = (props) => {
	
	let [, setPreloaderOn] = useState(false);
	let {authTh} = props;
	// хук для запроса на серв. списка пользователей. Производится запись пришедшего списка через CB
	useEffect(() => {
		setPreloaderOn(true);
		// запрос с параметром на кроссдоменную аутентификацию {withCredentials:true}
		authTh();
		setPreloaderOn(false);
	}, [authTh]);
	
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
	authTh,
})(HeaderContainer);



