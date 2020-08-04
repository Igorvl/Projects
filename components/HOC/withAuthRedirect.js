import React from "react";
import {Redirect} from "react-router-dom";
import {connect} from "react-redux";



 const withAuthRedirect = (Component) => {
	
	class RedirectComponent extends React.Component {
		render() {
			if (!this.props.isLoggedIn) return <Redirect to={'/login'}/>;
			return <Component {...this.props}/>
		}
	}
	
	 const mapStateToProps = (state) => {
		 return ({
			 isLoggedIn: state.auth.isLoggedIn,
		 })
	 };
	
	const AuthRedirect = connect(mapStateToProps, )(RedirectComponent);
	return AuthRedirect;
};

export default withAuthRedirect